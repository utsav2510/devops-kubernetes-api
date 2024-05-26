from kubernetes import client, config
from fastapi import FastAPI, HTTPException
from models import CreateAllResources, Namespace, HorizontalPodAutoscaler, Deployment, NodePortService
import re
import uvicorn


app = FastAPI(title="Kubernetes API", version="0.0.1")

# Load Kubernetes configuration
config.load_kube_config()

# Create a Kubernetes client

v1 = client.CoreV1Api()
appsv1 = client.AppsV1Api()
autoscalingv2 = client.AutoscalingV2Api()


@app.get("/namespaces", tags=["Namespace"])
def list_namespaces():
    try:
        namespaces = v1.list_namespace()
        return namespaces.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")

@app.post("/namespaces", tags=["Namespace"])
def create_namespace(namespace: Namespace):
    try:
        new_namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace.name), api_version="v1", kind="Namespace")
        created_namespace = v1.create_namespace(body=new_namespace)
        
        return created_namespace.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error creating namespace: {e}")

@app.delete("/namespaces/{name}", tags=["Namespace"])
def delete_namespace(name: str):
    try:
        deleted_namespace = v1.delete_namespace(name)
        return {"message": f"Namespace {name} deleted"}
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error deleting namespace: {e}")

@app.post("/hpa", tags=["HPA"])
def create_hpa(hpa: HorizontalPodAutoscaler):
    horizontalpodautoscaler = client.V2HorizontalPodAutoscaler(
        metadata=client.V1ObjectMeta(name= f"{hpa.deployment_name}-hpa"),
        kind="HorizontalPodAutoscaler",
        spec=client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=client.V2CrossVersionObjectReference(
                api_version="apps/v1",
                kind="Deployment",
                name= f"{hpa.deployment_name}"
            ),
            min_replicas=hpa.spec.min_replicas,
            max_replicas=hpa.spec.max_replicas,
            metrics= [
                client.V2MetricSpec(type="Resource",resource=client.V2ResourceMetricSource(
                    name="cpu",target=client.V2MetricTarget(average_utilization=hpa.spec.cpu_utilization_percentage,type="Utilization")
                )),
                client.V2MetricSpec(type="Resource",resource=client.V2ResourceMetricSource(
                    name="memory",target=client.V2MetricTarget(average_utilization=hpa.spec.memory_utilization_percentage,type="Utilization")
                ))
            ]            
        )
    )
    try:
        resp = autoscalingv2.create_namespaced_horizontal_pod_autoscaler(hpa.namespace.name, horizontalpodautoscaler)
        return resp.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error creating HPA: {e}")

@app.post("/service/nodeport", tags=["Service"])
def create_node_port_service(nps: NodePortService):
    try:
        service_container_ports_object = []
        for port_num in nps.ports:
                service_port_object = {"protocol": "TCP", "port": port_num, "targetPort": port_num,"name": f"p-{port_num}"}
                service_container_ports_object.append(service_port_object)

        service = client.CoreV1Api().create_namespaced_service(
                body={
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {"name": f"{nps.applabel}-nodeport"},
                    "spec": {
                        "selector": {"app": f"{nps.applabel}"},
                        "ports": service_container_ports_object,
                        "type": "NodePort"
                    }
                },
                namespace=f"{nps.namespace.name}"
            )
        return service.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")

@app.delete("/service/nodeport/{namespace}/{name}", tags=["Service"])
def delete_node_port_service(namespace:str,name:str):
    try:
        service = v1.delete_namespaced_service(name=name,namespace=namespace)
        return {"message": f"Service {namespace}/{name} deleted"}
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")


@app.get("/deployment/{namespace}/{uid}", tags=["Deployment"])
def get_deployment_by_uid(namespace:str, uid: str):
    try:
        deployments = appsv1.list_namespaced_deployment(namespace).items
        deployment = next((d for d in deployments if d.metadata.uid == uid), None)
        
        if deployment:
            selector = deployment.spec.selector.match_labels
            pods = v1.list_namespaced_pod(namespace, label_selector=','.join([f"{k}={v}" for k, v in selector.items()])).items
            
            health_status = {}
            for pod in pods:
                health_status[pod.metadata.name] = pod.status.phase

            return health_status
        else:
            raise HTTPException(status_code=404, detail=f"Error: Deployment not found")

    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")

@app.get("/deployment/{namespace}/{name}", tags=["Deployment"])
def get_deployment_by_name(namespace:str, name: str):
    try:
        deployment = appsv1.delete_namespaced_deployment(name=name,namespace=namespace)
        return deployment.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")
    
@app.delete("/deployment/{namespace}/{name}", tags=["Deployment"])
def delete_deployment(namespace:str,name:str):
    try:
        deployment = appsv1.delete_namespaced_deployment(name=name,namespace=namespace)
        return {"message": f"Deployment {namespace}/{name} deleted"}
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")

@app.post("/deployments", tags=["Deployment"])
def create_deployment(deployment: Deployment):
    try:
        
        deployment_container_ports_object = []
        
        for port_num in deployment.ports:
            deployment_port_object = {"containerPort": port_num}
            deployment_container_ports_object.append(deployment_port_object)

        deployment_set = appsv1.create_namespaced_deployment(
            body={
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": f"{deployment.name}"},
                "spec": {
                    "replicas": deployment.replicas,
                    "selector": {
                        "matchLabels": {"app": f"{deployment.name}"}
                    },
                    "template": {
                        "metadata": {"labels": {"app": f"{deployment.name}"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": f"{re.sub('[^A-Za-z0-9]+', '', deployment.name)}-{re.sub('[^A-Za-z0-9]+', '', deployment.image.name)}-{re.sub('[^A-Za-z0-9]+', '', deployment.image.tag)}",
                                    "image": f"{deployment.image.name}:{deployment.image.tag}",
                                    "ports": deployment_container_ports_object,
                                    "resources": {
                                        "requests": {
                                            "cpu": f"{deployment.resource.requests.cpu}",
                                            "memory": f"{deployment.resource.requests.memory}"
                                        },
                                        "limits": {
                                            "cpu": f"{deployment.resource.limits.cpu}",
                                            "memory": f"{deployment.resource.limits.memory}"
                                        }
                                    },
                                }
                            ]
                        }
                    }
                }
            },
            namespace= f"{deployment.namespace.name}"
        )
        
        return deployment_set.to_dict()
    except client.exceptions.ApiException as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")

@app.post("/createallresource", tags=["General"])
def create_all_resources(res: CreateAllResources):
    NameSpaceCreated = False
    DeploymentCreated = False
    ServiceCreated = False
    try:
        #Create namespace if it doesn't exist
        try:
            v1.read_namespace(name=res.deployment.namespace.name)
            
        except client.exceptions.ApiException as e:
            if e.status == 404:
                # Namespace does not exist, create it
                
                create_namespace(Namespace(name=res.deployment.namespace.name))
                NameSpaceCreated = True
            else:
                raise HTTPException(status_code=e.status, detail=f"Error creating namespace: {e}")
        
        #Create deployment set
        deployment = create_deployment(res.deployment)
        DeploymentCreated = True

        #Create Services
        service = create_node_port_service(NodePortService(namespace=res.deployment.namespace,ports=res.deployment.ports,applabel=res.deployment.name))
        ServiceCreated = True

        #Create HPA
        hpa = create_hpa(HorizontalPodAutoscaler(namespace=res.deployment.namespace,deployment_name=res.deployment.name,spec=res.horizontalpodautoscalerspec))
        
        return {"namespace": f"{res.deployment.namespace.name}", "deployment":deployment,"service": service, "horizontalpodautoscaler": hpa}

    except client.exceptions.ApiException as e:
        if(NameSpaceCreated):
            delete_namespace(res.deployment.namespace.name)
        else:
            if(DeploymentCreated):
                delete_deployment(namespace=res.deployment.namespace.name, name=res.deployment.name)
            if(ServiceCreated):
                delete_node_port_service(namespace=res.deployment.namespace.name, name=f"{res.deployment.name}-nodeport")
                
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")
    except Exception as e:
        raise HTTPException(status_code=e.status, detail=f"Error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


