# 🌐 Build Your Own Private Docker Registry (Ubuntu 22.04 LTS)

This guide demonstrates how to build a private Docker registry on **Ubuntu 22.04 LTS**, with Docker Hub pull-through cache support for use with tools like [Kind](https://kind.sigs.k8s.io/).

---

## 🔧 Step 1: Install Docker

Refer to the official documentation for more details: [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

### 🛠 Add Docker's GPG Key and Repository

```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

### 📦 Add Docker Repository to Apt Sources

```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update the package index
sudo apt-get update
```

### 🚀 Install Docker Engine and Components

```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

---

## 📦 Step 2: Run Docker Official Registry Image

Launch a local Docker registry that acts as a pull-through cache of Docker Hub:

```bash
docker run -d --restart=always --name registry-mirror \
  -p 5000:5000 \
  -v /opt/registry-cache:/var/lib/registry \
  -e REGISTRY_PROXY_REMOTEURL=https://registry-1.docker.io \
  registry:2
```

### 🔍 Explanation

- `--restart=always`: Automatically restarts the container if it stops or the system reboots.
- `-p 5000:5000`: Exposes registry on port 5000.
- `-v /opt/registry-cache:/var/lib/registry`: Persists cached layers.
- `REGISTRY_PROXY_REMOTEURL`: Enables proxy mode to Docker Hub.

---

## ⚙️ Step 3: Enable Kind Nodes to Use the Private Registry

Modify your Kind cluster config file to use the private registry mirror.

### ✏️ Example Kind Config

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
  - |
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
      endpoint = ["http://<your-docker-registry-host>:5000"]
```

> 🔄 **Replace `<your-docker-registry-host>`** with the IP address or hostname of your Docker registry server.

This configuration allows all nodes in the `kind` cluster to use the referred registry mirror for pulling images, improving speed and avoiding Docker Hub rate limits.

---

✅ **You're all set!** Your private Docker registry is now up and running with pull-through caching and is integrated with your Kind cluster.
