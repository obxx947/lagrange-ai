# ============================================================
# 拉格朗日AI — Ruby 脚本：API测试客户端
# 用法：ruby api_test.rb
# ============================================================

require 'net/http'
require 'json'
require 'uri'

BASE_URL = ENV.fetch('LAGRANGE_API', 'http://127.0.0.1:3000')

# API客户端类
class LagrangeAPI
  def initialize(base_url = BASE_URL)
    @base = URI(base_url)
    @token = nil
  end

  # 注册新用户
  def register(username, password)
    post('/api/register', { username: username, password: password })
  end

  # 登录
  def login(username, password)
    resp = post('/api/login', { username: username, password: password })
    @token = resp['access_token'] if resp
    resp
  end

  # 获取用户信息
  def user_info
    get('/api/user/me')
  end

  # 获取舰船数据
  def ships
    get('/api/ships')
  end

  # 健康检查
  def health
    get('/health')
  end

  private

  def headers
    h = { 'Content-Type' => 'application/json' }
    h['Authorization'] = "Bearer #{@token}" if @token
    h
  end

  def get(path)
    req = Net::HTTP::Get.new(path, headers)
    send_request(req)
  end

  def post(path, body)
    req = Net::HTTP::Post.new(path, headers)
    req.body = body.to_json
    send_request(req)
  end

  def send_request(req)
    http = Net::HTTP.new(@base.host, @base.port)
    http.open_timeout = 5
    http.read_timeout = 10
    resp = http.request(req)
    JSON.parse(resp.body) rescue { 'error' => resp.code }
  rescue StandardError => e
    { 'error' => e.message }
  end
end

# 主程序
if __FILE__ == $0
  puts "=" * 50
  puts "  拉格朗日AI — Ruby API测试"
  puts "=" * 50
  puts "  服务: #{BASE_URL}"
  puts

  api = LagrangeAPI.new

  # 健康检查
  health = api.health
  if health['status'] == 'healthy'
    puts "  ✅ 服务运行中"
  else
    puts "  ❌ 服务不可用: #{health['error']}"
    exit 1
  end

  # 舰船数据
  ships = api.ships
  puts "  🚀 舰船: #{ships['count']} 艘"
  puts "  📚 索引: #{health['index_built'] ? '已构建' : '未构建'}"
  puts
  puts "=" * 50
end
