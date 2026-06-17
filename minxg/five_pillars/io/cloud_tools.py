"""
"""
from __future__ import annotations
from typing import Dict
from minxg.base import BaseWorker, tool


class CloudToolsWorker(BaseWorker):
    worker_id = "cloud_tools"
    version = "1.0.0"

    @tool(description="AWS EC2 instance type recommendation", category="aws")
    async def ec2_instance_recommend(self, purpose: str, vcpu: int = 2, memory_gb: int = 4) -> Dict:
        types = {
            "web": "t3.medium", "compute": "c5.large", "memory": "r5.large",
            "gpu": "g4dn.xlarge", "storage": "i3.large", "general": "t3.medium",
        }
        inst = types.get(purpose, "t3.medium")
        pricing = {"t3.medium": 0.0416, "c5.large": 0.085, "r5.large": 0.126,
                   "g4dn.xlarge": 0.526, "i3.large": 0.156}
        hourly = pricing.get(inst, 0.05)
        return {"instance": inst, "purpose": purpose, "hourly_usd": hourly,
                "monthly_usd": round(hourly * 730, 2), "vcpu": vcpu, "memory_gb": memory_gb}

    @tool(description="Cloud storage cost estimation", category="storage")
    async def storage_cost(self, total_gb: float, provider: str = "aws") -> Dict:
        pricing = {
            "aws_s3": 0.023, "aws_s3_ia": 0.0125, "aws_glacier": 0.004,
            "gcp": 0.020, "azure": 0.018, "cloudflare_r2": 0.015,
        }
        price = pricing.get(provider, 0.02)
        return {"provider": provider, "total_gb": total_gb,
                "monthly_usd": round(total_gb * price, 2),
                "yearly_usd": round(total_gb * price * 12, 2)}

    @tool(description="Cloud zone latency estimation", category="network")
    async def cloud_latency(self, zone: str) -> Dict:
        estimates = {
            "cn-north-1": 5, "cn-northwest-1": 8, "ap-northeast-1": 40,
            "ap-southeast-1": 50, "us-east-1": 200, "us-west-2": 160,
            "eu-west-1": 220, "eu-central-1": 200, "me-south-1": 180,
        }
        lat = estimates.get(zone, 100)
        return {"zone": zone, "estimated_rtt_ms": lat,
                "recommended_for": "low latency" if lat < 50 else ("acceptable" if lat < 150 else "high latency")}

    @tool(description="Docker Compose template generation", category="docker")
    async def docker_compose(self, service_name: str, image: str, port: int = 8080,
                              env: dict = None) -> Dict:
        lines = [f"version: '3.8'", "services:", f"  {service_name}:",
                 f"    image: {image}", f"    ports:", f"      - \"{port}:{port}\""]
        if env:
            lines.append("    environment:")
            for k, v in (env or {}).items():
                lines.append(f"      - {k}={v}")
        lines.append("    restart: unless-stopped")
        return {"yaml": "\n".join(lines), "service": service_name}

    @tool(description="Dockerfile template generation", category="docker")
    async def dockerfile(self, base: str = "python:3.12-slim", cmd: str = "python app.py",
                          deps: str = "") -> Dict:
        lines = [f"FROM {base}", "WORKDIR /app"]
        if deps:
            lines.append(f"RUN pip install {deps}")
        lines.append("COPY . .")
        lines.append(f'CMD ["{cmd.replace(" ", '", "')}"]')
        return {"dockerfile": "\n".join(lines), "base_image": base}

    @tool(description="Kubernetes Deployment template generation", category="k8s")
    async def k8s_deployment(self, name: str, image: str, replicas: int = 1, port: int = 8080) -> Dict:
        yaml = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {image}
        ports:
        - containerPort: {port}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}-svc
spec:
  selector:
    app: {name}
  ports:
  - port: {port}
    targetPort: {port}
  type: ClusterIP"""
        return {"yaml": yaml, "name": name, "kind": "Deployment+Service"}

    @tool(description="systemd service unit template", category="linux")
    async def systemd_unit(self, name: str, exec_start: str, description: str = "",
                            user: str = "nobody") -> Dict:
        unit = f"""[Unit]
Description={description or name}
After=network.target

[Service]
Type=simple
User={user}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"""
        return {"unit": unit, "name": name, "install_cmd": f"sudo systemctl enable --now {name}"}

    @tool(description="Nginx reverse proxy config generation", category="nginx")
    async def nginx_proxy(self, domain: str, upstream_port: int = 8080, ssl: bool = True) -> Dict:
        ssl_block = ""
        if ssl:
            ssl_block = f"""
    listen 443 ssl http2;
    ssl_certificate /etc/ssl/{domain}.pem;
    ssl_certificate_key /etc/ssl/{domain}.key;"""
        conf = f"""server {{
    listen 80;
    server_name {domain};{ssl_block}

    location / {{
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}"""
        return {"nginx_config": conf, "domain": domain, "port": upstream_port, "ssl": ssl}

    @tool(description="Calculate CDN bandwidth cost", category="cdn")
    async def cdn_cost(self, monthly_gb: float, provider: str = "cloudflare") -> Dict:
        pricing = {"cloudflare": 0.0, "aws_cloudfront": 0.085, "fastly": 0.12, "bunny": 0.01}
        rate = pricing.get(provider, 0.05)
        return {"provider": provider, "monthly_gb": monthly_gb,
                "monthly_cost_usd": round(monthly_gb * rate, 2),
                "first_10tb_free": provider == "cloudflare"}

    @tool(description="logrotate config generation", category="linux")
    async def logrotate_config(self, log_path: str, rotate: int = 7, size: str = "100M") -> Dict:
        conf = f"""{log_path} {{
    daily
    rotate {rotate}
    size {size}
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
}}"""
        return {"config": conf, "path": log_path, "rotate_count": rotate}

    @tool(description="Health check endpoint template", category="ops")
    async def health_check_config(self, endpoint: str = "/health", interval_sec: int = 30,
                                   timeout_sec: int = 5, healthy_threshold: int = 3) -> Dict:
        return {"endpoint": endpoint, "interval_sec": interval_sec, "timeout_sec": timeout_sec,
                "healthy_threshold": healthy_threshold, "unhealthy_threshold": 3,
                "curl": f"curl -f http://localhost:8080{endpoint}"}

    @tool(description=".env file template generation", category="config")
    async def env_template(self, app_name: str = "app") -> Dict:
        content = f"""# {app_name} Configuration
ENV=production
DEBUG=false
LOG_LEVEL=info

HOST=0.0.0.0
PORT=8080

DB_HOST=localhost
DB_PORT=5432
DB_NAME={app_name}
DB_USER={app_name}
DB_PASSWORD=***

"""

        return {"content": content, "app_name": app_name}
