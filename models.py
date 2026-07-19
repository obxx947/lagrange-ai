# -*- coding: utf-8 -*-
"""
Pydantic 数据模型
----------------
定义所有 API 请求/响应的数据结构，用于 FastAPI 自动校验和文档生成。
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== 认证相关模型 ====================

class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=2, max_length=32, description="用户名（2-32字符）")
    password: str = Field(..., min_length=4, max_length=64, description="密码（4-64字符）")


class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """登录成功返回的Token响应"""
    access_token: str = Field(..., description="JWT访问凭证")
    token_type: str = Field(default="bearer", description="Token类型")
    expires_in: int = Field(..., description="有效期（秒）")
    username: str = Field(..., description="用户名")
    platform_tokens: int = Field(..., description="用户剩余平台Token")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    platform_tokens: int
    deepseek_input_tokens: int
    deepseek_output_tokens: int
    created_at: str


# ==================== AI 对话相关模型 ====================

class ChatRequest(BaseModel):
    """AI 对话请求"""
    message: str = Field(..., min_length=1, max_length=4000, description="用户提问内容")
    history: Optional[List[dict]] = Field(default=[], description="多轮对话历史上下文")


class SourceDoc(BaseModel):
    """引用资料来源"""
    file_name: str = Field(..., description="文件名")
    snippet: str = Field(..., description="相关文本片段")


class ChatResponse(BaseModel):
    """AI 对话响应"""
    answer: str = Field(..., description="AI 回复内容")
    source_docs: List[SourceDoc] = Field(default=[], description="引用的资料来源")
    prompt_tokens: int = Field(..., description="本次消耗输入Token")
    completion_tokens: int = Field(..., description="本次消耗输出Token")
    total_tokens: int = Field(..., description="本次总消耗Token")
    platform_tokens_remaining: int = Field(..., description="用户剩余平台Token")


# ==================== 模拟器相关模型 ====================

class SimulatorSaveRequest(BaseModel):
    """模拟器存档保存请求"""
    save_name: str = Field(..., min_length=1, max_length=64, description="存档名称")
    fleet_config: dict = Field(..., description="舰队配置（完整JSON对象）")


class SimulatorSaveResponse(BaseModel):
    """模拟器存档响应"""
    id: int
    save_name: str
    fleet_config: dict
    created_at: str
    updated_at: str


class SimulatorAnalyzeRequest(BaseModel):
    """模拟器AI战术分析请求"""
    fleet_config: dict = Field(..., description="舰队配置")
    battle_mode: str = Field(default="escort", description="战斗模式：escort/bomb")


class SimulatorAnalyzeResponse(BaseModel):
    """模拟器AI分析响应"""
    analysis: str = Field(..., description="AI战术分析结果")
    source_docs: List[SourceDoc] = Field(default=[], description="引用资料来源")
    prompt_tokens: int = Field(..., description="消耗输入Token")
    completion_tokens: int = Field(..., description="消耗输出Token")
    total_tokens: int = Field(..., description="总消耗Token")
    platform_tokens_remaining: int = Field(..., description="剩余平台Token")


# ==================== 管理员相关模型 ====================

class AdminLoginRequest(BaseModel):
    """管理员登录请求"""
    password: str = Field(..., description="管理员密码")


class RechargeRequest(BaseModel):
    """充值请求"""
    target_username: str = Field(..., description="目标用户名")
    amount: int = Field(..., gt=0, le=1000000, description="充值Token数量（1-100万）")


class RechargeLogResponse(BaseModel):
    """充值日志响应"""
    id: int
    admin_id: int
    target_user_id: int
    amount: int
    created_at: str


class AdminLoginResponse(BaseModel):
    """管理员登录响应"""
    access_token: str
    token_type: str = "bearer"
    message: str


# ==================== 通用响应模型 ====================

class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
    error_code: Optional[str] = Field(default=None, description="错误代码")
