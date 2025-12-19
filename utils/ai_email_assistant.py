"""
AIEmailAssistant - AI邮件助手
实现一键生成邮件和按要求生成邮件功能
"""
import json
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass

from models.ai_configuration import AIConfiguration


@dataclass
class EmailGenerationResult:
    """邮件生成结果"""
    success: bool
    content: str
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'content': self.content,
            'error_message': self.error_message
        }


class AIEmailAssistant:
    """
    AI邮件助手
    
    实现一键生成邮件和按要求生成邮件功能
    """
    
    DEFAULT_TIMEOUT = 10  # 10秒超时
    MAX_RETRIES = 2
    
    # 默认邮件生成提示词
    DEFAULT_PROMPT = """请为我生成一封专业的商务邮件，用于向潜在客户介绍我们的产品或服务。
邮件应该：
1. 简洁明了，不超过200字
2. 语气专业友好
3. 包含明确的行动号召
4. 适合B2B营销场景"""
    
    def __init__(self, config: AIConfiguration):
        """
        初始化AI邮件助手
        
        Args:
            config: AI配置对象
        """
        self._config = config
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(
            self._config.api_endpoint and 
            self._config.api_key and 
            self._config.model
        )

    def generate_email(self, context: Optional[Dict[str, Any]] = None) -> EmailGenerationResult:
        """
        一键生成邮件内容
        
        Args:
            context: 可选的上下文信息（如商家名称、产品等）
            
        Returns:
            EmailGenerationResult: 生成结果
        """
        if not self.is_configured:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='AI服务未配置，请先在设置中配置API信息'
            )
        
        prompt = self._build_default_prompt(context)
        return self._call_ai_api(prompt)
    
    def generate_with_requirements(
        self, 
        requirements: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> EmailGenerationResult:
        """
        根据要求生成邮件内容
        
        Args:
            requirements: 用户的具体要求
            context: 可选的上下文信息
            
        Returns:
            EmailGenerationResult: 生成结果
        """
        if not self.is_configured:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='AI服务未配置，请先在设置中配置API信息'
            )
        
        if not requirements or not requirements.strip():
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='请输入邮件生成要求'
            )
        
        prompt = self._build_requirements_prompt(requirements, context)
        return self._call_ai_api(prompt)
    
    def _build_default_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """构建默认提示词"""
        prompt = self.DEFAULT_PROMPT
        
        if context:
            context_info = []
            if context.get('business_name'):
                context_info.append(f"目标客户: {context['business_name']}")
            if context.get('product'):
                context_info.append(f"产品/服务: {context['product']}")
            if context.get('industry'):
                context_info.append(f"行业: {context['industry']}")
            
            if context_info:
                prompt += f"\n\n上下文信息:\n" + "\n".join(context_info)
        
        return prompt
    
    def _build_requirements_prompt(
        self, 
        requirements: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建带要求的提示词"""
        prompt = f"""请根据以下要求生成一封邮件：

用户要求：
{requirements}

请确保邮件：
1. 符合用户的具体要求
2. 语气专业友好
3. 结构清晰"""
        
        if context:
            context_info = []
            if context.get('business_name'):
                context_info.append(f"目标客户: {context['business_name']}")
            if context.get('product'):
                context_info.append(f"产品/服务: {context['product']}")
            if context.get('industry'):
                context_info.append(f"行业: {context['industry']}")
            
            if context_info:
                prompt += f"\n\n上下文信息:\n" + "\n".join(context_info)
        
        return prompt

    def _call_ai_api(self, prompt: str) -> EmailGenerationResult:
        """
        调用AI API生成内容
        
        Args:
            prompt: 提示词
            
        Returns:
            EmailGenerationResult: 生成结果
        """
        # 解密API密钥
        api_key = AIConfiguration.decrypt_key(self._config.api_key)
        if not api_key:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='API密钥无效'
            )
        
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                result = self._make_request(api_key, prompt)
                return result
            except requests.exceptions.Timeout:
                last_error = 'API请求超时，请稍后重试'
            except requests.exceptions.ConnectionError:
                last_error = '无法连接到AI服务，请检查网络连接'
            except requests.exceptions.RequestException as e:
                last_error = f'API请求失败: {str(e)}'
            except Exception as e:
                last_error = f'生成邮件时发生错误: {str(e)}'
        
        return EmailGenerationResult(
            success=False,
            content='',
            error_message=last_error
        )
    
    def _make_request(self, api_key: str, prompt: str) -> EmailGenerationResult:
        """
        发送API请求
        
        Args:
            api_key: 解密后的API密钥
            prompt: 提示词
            
        Returns:
            EmailGenerationResult: 生成结果
        """
        import sys
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        # 构建请求体（兼容智谱AI和OpenAI格式）
        payload = {
            'model': self._config.model,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的商务邮件写作助手，擅长撰写简洁、专业、有说服力的商务邮件。请直接输出邮件内容，不要添加额外的解释。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'stream': False,
            'do_sample': True,
            'top_p': 0.95,
            'response_format': {'type': 'text'}
        }
        
        print(f"[AI] 请求URL: {self._config.api_endpoint}", file=sys.stderr)
        print(f"[AI] 请求模型: {self._config.model}", file=sys.stderr)
        
        try:
            response = requests.post(
                self._config.api_endpoint,
                headers=headers,
                json=payload,
                timeout=30  # 增加超时时间
            )
            
            print(f"[AI] 响应状态码: {response.status_code}", file=sys.stderr)
            print(f"[AI] 响应内容: {response.text[:500] if response.text else 'empty'}", file=sys.stderr)
            
        except requests.exceptions.Timeout:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='API请求超时，请稍后重试'
            )
        except requests.exceptions.ConnectionError as e:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message=f'无法连接到AI服务: {str(e)}'
            )
        except Exception as e:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message=f'请求异常: {str(e)}'
            )
        
        if response.status_code == 401:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='API密钥无效或已过期'
            )
        
        if response.status_code == 429:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message='API请求频率超限，请稍后重试'
            )
        
        if response.status_code != 200:
            error_msg = f'API返回错误: HTTP {response.status_code}'
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = f"API错误: {error_data['error'].get('message', str(error_data['error']))}"
            except Exception:
                pass
            return EmailGenerationResult(
                success=False,
                content='',
                error_message=error_msg
            )
        
        try:
            data = response.json()
            content = self._extract_content(data)
            
            print(f"[AI] 提取的内容长度: {len(content) if content else 0}", file=sys.stderr)
            
            if content:
                return EmailGenerationResult(
                    success=True,
                    content=content
                )
            else:
                return EmailGenerationResult(
                    success=False,
                    content='',
                    error_message='AI返回的内容为空，请重试'
                )
        except json.JSONDecodeError as e:
            return EmailGenerationResult(
                success=False,
                content='',
                error_message=f'无法解析API响应: {str(e)}'
            )
    
    def _extract_content(self, data: dict) -> str:
        """
        从API响应中提取内容
        
        Args:
            data: API响应数据
            
        Returns:
            str: 提取的内容
        """
        import sys
        
        print(f"[AI] 解析响应数据: {json.dumps(data, ensure_ascii=False)[:1000]}", file=sys.stderr)
        
        # OpenAI/智谱AI 格式: choices[0].message.content
        if 'choices' in data and len(data['choices']) > 0:
            choice = data['choices'][0]
            
            # 标准格式: message.content
            if 'message' in choice:
                message = choice['message']
                if isinstance(message, dict) and 'content' in message:
                    content = message['content']
                    if content:
                        print(f"[AI] 从 choices[0].message.content 提取内容", file=sys.stderr)
                        return content.strip()
            
            # 备用格式: delta.content (流式响应)
            if 'delta' in choice:
                delta = choice['delta']
                if isinstance(delta, dict) and 'content' in delta:
                    content = delta['content']
                    if content:
                        print(f"[AI] 从 choices[0].delta.content 提取内容", file=sys.stderr)
                        return content.strip()
            
            # 旧格式: text
            if 'text' in choice:
                content = choice['text']
                if content:
                    print(f"[AI] 从 choices[0].text 提取内容", file=sys.stderr)
                    return content.strip()
        
        # 其他可能的格式
        if 'content' in data:
            content = data['content']
            if content:
                print(f"[AI] 从 data.content 提取内容", file=sys.stderr)
                return content.strip()
        
        if 'text' in data:
            content = data['text']
            if content:
                print(f"[AI] 从 data.text 提取内容", file=sys.stderr)
                return content.strip()
        
        if 'response' in data:
            content = data['response']
            if content:
                print(f"[AI] 从 data.response 提取内容", file=sys.stderr)
                return content.strip()
        
        # 智谱AI 可能的其他格式
        if 'data' in data:
            inner_data = data['data']
            if isinstance(inner_data, dict):
                if 'choices' in inner_data:
                    return self._extract_content(inner_data)
                if 'content' in inner_data:
                    return inner_data['content'].strip()
        
        print(f"[AI] 无法从响应中提取内容", file=sys.stderr)
        return ''
