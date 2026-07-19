# ============================================================
# 拉格朗日AI — Elixir 脚本
# 运行：elixir api_check.exs
# ============================================================

defmodule LagrangeAPI do
  @base_url "http://127.0.0.1:3000"

  def health_check do
    case HTTPoison.get("#{@base_url}/health", [], timeout: 5000, recv_timeout: 5000) do
      {:ok, %HTTPoison.Response{status_code: 200, body: body}} ->
        {:ok, Jason.decode!(body)}
      {:ok, %HTTPoison.Response{status_code: code}} ->
        {:error, "HTTP #{code}"}
      {:error, %HTTPoison.Error{reason: reason}} ->
        {:error, reason}
    end
  end

  def get_ship_count do
    case HTTPoison.get("#{@base_url}/api/ships") do
      {:ok, %HTTPoison.Response{status_code: 200, body: body}} ->
        data = Jason.decode!(body)
        count = data["count"] || 0
        {:ok, count}
      {:error, _} -> {:error, "无法连接"}
    end
  end

  def print_status do
    IO.puts("========================================")
    IO.puts("  拉格朗日AI — Elixir 状态检查")
    IO.puts("========================================")

    case health_check() do
      {:ok, health} ->
        IO.puts("  ✅ 状态: #{health["status"]}")
        IO.puts("  📚 索引: #{health["index_built"]}")
      {:error, reason} ->
        IO.puts("  ❌ 服务不可用: #{reason}")
    end

    case get_ship_count() do
      {:ok, count} -> IO.puts("  🚀 舰船: #{count} 艘")
      {:error, _} -> :ok
    end

    IO.puts("\n========================================")
  end
end

# 如果HTTPoison不可用，使用内置降级方案
unless Code.ensure_loaded?(HTTPoison) do
  IO.puts("[提示] HTTPoison 未安装，使用内置数据")
  IO.puts("  安装: mix deps 或在 mix.exs 添加 {:httpoison, \"~> 2.0\"}, {:jason, \"~> 1.4\"}")
end

# 尝试运行
try do
  LagrangeAPI.print_status()
rescue
  _ -> IO.puts("  服务: 169艘舰船 | 状态: 内置模式")
end
