from kubernetes import client, config


# Load Kubernetes configuration
config.load_kube_config(config_file=".\\config")

# Create a Kubernetes client
v1 = client.CoreV1Api()

