# ============================================================
# 拉格朗日AI — Julia 脚本：战斗统计分析
# 运行：julia battle_stats.jl
# ============================================================

using JSON
using Statistics
using Printf

const BASE_URL = get(ENV, "LAGRANGE_API", "http://127.0.0.1:3000")

# 舰船数据加载（备选：直接读JSON文件）
function load_ships_from_file()
    json_path = joinpath(@__DIR__, "lagrange_docs", "ship_database.json")
    if isfile(json_path)
        data = JSON.parsefile(json_path)
        return data
    else
        println("  [提示] JSON文件未找到，使用内置数据")
        return nothing
    end
end

# HP统计分析
function analyze_hp_stats(ships::Vector)
    hp_values = [s["hp"] for s in ships if haskey(s, "hp")]
    
    println("="^50)
    println("  拉格朗日AI — Julia 舰船HP分析")
    println("="^50)
    println("  舰船数: $(length(ships))")
    println()
    
    println("  HP统计:")
    @printf("    平均: %'.0f\n", mean(hp_values))
    @printf("    中位数: %'.0f\n", median(hp_values))
    @printf("    最大: %'.0f\n", maximum(hp_values))
    @printf("    最小: %'.0f\n", minimum(hp_values))
    @printf("    标准差: %'.0f\n", std(hp_values))
    println()
    
    # 按类型分组统计
    println("  类型分布:")
    type_groups = Dict{String,Vector}()
    for s in ships
        t = get(s, "type", "unknown")
        push!(get!(type_groups, t, []), s)
    end
    
    type_names = Dict(
        "battleship" => "战列舰", "battlecruiser" => "战巡",
        "aircraftcarrier" => "航母", "support" => "支援舰",
        "cruiser" => "巡洋舰", "destroyer" => "驱逐舰",
        "frigate" => "护卫舰", "fighter" => "战机", "corvette" => "护航艇"
    )
    
    for (t, group) in sort(collect(type_groups), by=x->length(x[2]), rev=true)
        name = get(type_names, t, t)
        cnt = length(group)
        avg_hp = mean([s["hp"] for s in group if haskey(s, "hp")])
        @printf("    %-10s %3d 艘  平均HP: %'.0f\n", name, cnt, avg_hp)
    end
    
    println("\n" * "="^50)
end

# 主程序
println("启动 Julia 分析引擎...")
ships = load_ships_from_file()

if ships !== nothing && length(ships) > 0
    analyze_hp_stats(ships)
else
    # 内置数据
    builtin = [
        Dict("name"=>"光追级","type"=>"cruiser","hp"=>85000),
        Dict("name"=>"CV3000级","type"=>"aircraftcarrier","hp"=>240000),
        Dict("name"=>"永恒风暴级","type"=>"battlecruiser","hp"=>320000),
    ]
    println("  使用内置数据 (3艘样例)")
    analyze_hp_stats(builtin)
end
