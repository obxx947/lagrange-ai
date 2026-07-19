# -*- coding: utf-8 -*-
"""
定时任务模块
-----------
提供自动清理过期数据和数据库备份的后台任务。
包含 APScheduler 或简单的后台线程实现。
"""

import asyncio
import threading
import time
from datetime import datetime

from database import cleanup_expired_data, backup_database

# ==================== 调度器控制 ====================
_scheduler_running = False
_scheduler_thread = None


def start_scheduler():
    """
    启动后台定时任务调度器
    
    定时任务列表：
    - 每小时执行一次数据清理（7天会话 + 14天聊天记录）
    - 每天凌晨 3:00 执行一次数据库自动备份
    """
    global _scheduler_running, _scheduler_thread
    
    if _scheduler_running:
        print("[调度器] 已经在运行中")
        return
    
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    print("[调度器] 后台定时任务已启动（每小时清理 + 每日备份）")


def stop_scheduler():
    """停止定时任务调度器"""
    global _scheduler_running
    _scheduler_running = False
    print("[调度器] 已停止")


def _scheduler_loop():
    """调度器主循环"""
    last_cleanup_hour = -1
    last_backup_day = -1
    
    while _scheduler_running:
        now = datetime.now()
        
        # 每小时执行清理（在整点过5分钟后触发）
        if now.hour != last_cleanup_hour and now.minute >= 5:
            try:
                print(f"[调度器] 执行定时清理...")
                cleanup_expired_data()
                last_cleanup_hour = now.hour
            except Exception as e:
                print(f"[调度器] 清理失败：{e}")
        
        # 每天凌晨3点执行备份
        if now.hour == 3 and now.day != last_backup_day and now.minute >= 10:
            try:
                print(f"[调度器] 执行每日数据库备份...")
                backup_database()
                last_backup_day = now.day
            except Exception as e:
                print(f"[调度器] 备份失败：{e}")
        
        # 每分钟检查一次
        time.sleep(60)
