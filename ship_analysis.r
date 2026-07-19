# ============================================================
# 拉格朗日AI — R 语言统计分析脚本
# 用法：Rscript ship_analysis.r
# 功能：舰船数据统计分析、可视化数据准备
# ============================================================

cat("========================================\n")
cat("  拉格朗日AI — R 舰船数据分析\n")
cat("========================================\n\n")

# 尝试读取JSON（需要 jsonlite 包）
has_jsonlite <- requireNamespace("jsonlite", quietly = TRUE)

if (has_jsonlite) {
  ships <- jsonlite::fromJSON("lagrange_docs/ship_database.json")
  cat(sprintf("  ✅ 已加载 %d 艘舰船\n\n", nrow(ships)))
  
  # 按类型统计
  cat("  类型分布:\n")
  type_table <- table(ships$type)
  type_names <- c(
    battleship = "战列舰", battlecruiser = "战巡",
    aircraftcarrier = "航母", support = "支援舰",
    cruiser = "巡洋舰", destroyer = "驱逐舰",
    frigate = "护卫舰", fighter = "战机", corvette = "护航艇"
  )
  for (t in names(type_table)) {
    name <- ifelse(t %in% names(type_names), type_names[t], t)
    cat(sprintf("    %-10s %3d 艘\n", name, type_table[t]))
  }
  
  # HP统计
  cat(sprintf("\n  HP统计:\n"))
  cat(sprintf("    平均: %,.0f\n", mean(ships$hp, na.rm = TRUE)))
  cat(sprintf("    最大: %,.0f (%s)\n", max(ships$hp, na.rm = TRUE),
      ships$name[which.max(ships$hp)]))
  cat(sprintf("    最小: %,.0f (%s)\n", min(ships$hp, na.rm = TRUE),
      ships$name[which.min(ships$hp)]))
  
  # 评级分布
  if ("ratings" %in% names(ships)) {
    cat("\n  评级分布(对舰):\n")
    # 提取antiShip评级
    anti_ship <- sapply(ships$ratings, function(r) if(is.list(r)) r$antiShip else NA)
    print(table(anti_ship))
  }
  
} else {
  cat("  [提示] jsonlite 包未安装，使用内置数据\n")
  cat("  安装: install.packages('jsonlite')\n\n")
  
  # 内置数据
  types <- c(战列舰=1, 战列巡洋舰=10, 航空母舰=5, 支援舰=2,
             巡洋舰=42, 驱逐舰=42, 护卫舰=36, 战机=9, 护航艇=22)
  for (name in names(types)) {
    cat(sprintf("    %-10s %3d 艘\n", name, types[name]))
  }
  cat(sprintf("\n    总计:        %d 艘\n", sum(types)))
}

cat("\n========================================\n")
