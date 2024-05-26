from pydantic import BaseModel, field_validator
from typing import List

class Namespace(BaseModel):
    name: str = 'default'
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "my-namespace"
                }
            ]
        }
    }

class Image(BaseModel):
    name: str
    tag: str = 'latest'
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "nginxdemos/hello",
                    "tag":"latest"
                }
            ]
        }
    }

class Resources(BaseModel):
    cpu: str
    memory: str
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "cpu": "100m",
                    "memory": "128Mi"
                }
            ]
        }
    }

class ResourcesRequest(BaseModel):
    requests: Resources
    limits: Resources

class HorizontalPodAutoscalerSpec(BaseModel):
    min_replicas: int = 1
    max_replicas: int = 10
    cpu_utilization_percentage: int = 80
    memory_utilization_percentage: int = 80

class HorizontalPodAutoscaler(BaseModel):
    namespace: Namespace
    deployment_name: str
    spec: HorizontalPodAutoscalerSpec

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "namespace": "default",
                    "deployment_name": "deployment-1",
                    "spec": {
                        "min_replicas": 1,
                        "max_replicas": 10,
                        "cpu_utilization_percentage": 80,
                        "memory_utilization_percentage": 80
                    }
                }
            ]
        }
    }

class Deployment(BaseModel):
    name: str
    namespace: Namespace = {"name": "default"}
    image: Image
    replicas: int = 1
    ports: List[int]
    resource: ResourcesRequest    

    @field_validator('ports')
    def values_must_be_unique(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Ports in the list must be unique')
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "deployment-1",
                    "namespace": {
                        "name": "my-namespace"
                    },
                    "image": {
                        "name": "nginxdemos/hello",
                        "tag": "latest"
                    },
                    "replicas": 2,
                    "ports": [
                        80
                    ],
                    "resource": {
                        "requests": {
                            "cpu": "100m",
                            "memory": "128Mi"
                        },
                        "limits": {
                            "cpu": "200m",
                            "memory": "256Mi"
                        }
                    }

                }
            ]
        }
    }

class NodePortService(BaseModel):
    namespace: Namespace
    ports: List[int]
    applabel: str

    @field_validator('ports')
    def check_non_empty_list(cls, v):
        if not v:
            raise ValueError('Port list must not be empty')
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "namespace": {
                        "name": "my-namespace"
                    },
                    "ports": [
                        80
                    ],
                    "applabel": "deployment-1"

                }
            ]
        }
    }

class CreateAllResources(BaseModel):
    deployment: Deployment
    horizontalpodautoscalerspec: HorizontalPodAutoscalerSpec
    