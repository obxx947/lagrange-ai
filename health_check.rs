/// ============================================================
/// 拉格朗日AI — Rust 工具
/// 编译：rustc -o lagrange_health.exe health_check.rs
/// 功能：异步HTTP健康检查
/// ============================================================

use std::env;
use std::time::Duration;

const DEFAULT_URL: &str = "http://127.0.0.1:3000/health";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = env::args()
        .nth(1)
        .unwrap_or_else(|| DEFAULT_URL.to_string());

    println!("========================================");
    println!("  拉格朗日AI — Rust 健康检查");
    println!("========================================");
    println!("  目标: {}\n", url);

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()?;

    match client.get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            println!("  ✅ HTTP {}", status);
            println!("  响应: {}", body);
        }
        Err(e) => {
            println!("  ❌ 连接失败: {}", e);
            println!("  💡 请先启动服务: python main.py");
        }
    }

    println!("\n========================================");
    Ok(())
}
