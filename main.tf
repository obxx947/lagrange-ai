# ============================================================
# 拉格朗日AI — Terraform 基础设施即代码
# 用法：terraform init && terraform apply
# ============================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

# 本地文件资源
resource "local_file" "env_config" {
  filename = "${path.module}/.env.generated"
  content  = <<-EOT
    DEEPSEEK_API_KEY=${var.deepseek_api_key}
    DEEPSEEK_BASE_URL=https://api.deepseek.com
    ADMIN_PASSWORD=${var.admin_password}
    JWT_SECRET=${var.jwt_secret}
    HOST=0.0.0.0
    PORT=${var.port}
    DATABASE_PATH=./lagrange.db
    CHROMA_DB_PATH=./chroma_db
    LAGRANGE_DOCS_PATH=./lagrange_docs
    DESKTOP_MATERIALS_PATH=C:/Users/Administrator/Desktop/质料
  EOT
}

resource "local_file" "service_bat" {
  filename = "${path.module}/启动服务_terraform.bat"
  content  = <<-EOT
    @echo off
    set PATH=D:\\Python312;D:\\Python312\\Scripts;%PATH%
    cd /d ${path.module}
    python main.py
    pause
  EOT
}

# 变量定义
variable "deepseek_api_key" {
  description = "DeepSeek API 密钥"
  type        = string
  sensitive   = true
  default     = "sk-placeholder"
}

variable "admin_password" {
  description = "管理员密码"
  type        = string
  sensitive   = true
  default     = "admin_lagrange_2024"
}

variable "jwt_secret" {
  description = "JWT 签名密钥"
  type        = string
  sensitive   = true
  default     = "lagrange-jwt-secret"
}

variable "port" {
  description = "服务端口"
  type        = number
  default     = 3000
}

# 输出
output "access_url" {
  value = "http://127.0.0.1:${var.port}"
}
