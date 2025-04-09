"""
LLM分析器模块 - 使用大语言模型分析帖子内容
"""

import json
from openai import OpenAI
from loguru import logger

class LLMAnalyzer:
    """LLM分析器类，负责调用大语言模型API进行内容分析"""
    
    def __init__(self, config):
        """
        初始化LLM分析器
        
        Args:
            config: LLM配置对象，包含api_key、base_url、provider和model字段
        """
        self.config = config
        
        # 如果未配置LLM，则禁用分析功能
        if not config:
            self.enabled = False
            logger.warning("未配置LLM，内容分析功能将被禁用")
            return
            
        self.enabled = True
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.model = config.model
        self.timeout = 30  # 默认API调用超时时间（秒）
        
        # 初始化OpenAI客户端
        try:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,  # 设置超时时间
            )
            logger.info(f"已初始化LLM客户端，使用模型: {self.model}")
        except Exception as e:
            self.enabled = False
            logger.error(f"初始化LLM客户端失败: {e}")
    
    def analyze_post(self, title, price_field, content, timeout=30):
        """
        分析帖子内容，提取商品和价格信息
        
        Args:
            title: 帖子标题
            price_field: 帖子中的价格字段
            content: 帖子主楼内容
            timeout: API调用超时时间（秒）
            
        Returns:
            dict: 分析结果字典，包含提取的商品列表
        """
        if not self.enabled:
            logger.warning("LLM分析功能未启用，跳过内容分析")
            return {"items": []}
        
        # 如果内容为空或占位符，则跳过分析
        if not content or content == '-' or content == "无法提取帖子内容":
            logger.warning("帖子内容为空或无法提取，跳过LLM分析")
            return {"items": []}
            
        try:
            # 构建系统提示
            system_prompt = """
            你是一个专门提取二手交易帖子结构化信息的AI助手。
            分析提供的帖子标题、价格信息和内容。
            识别出所有正在出售的商品及其对应的价格。
            只返回一个有效的JSON对象，不要包含任何解释性文本。
            JSON对象应该有一个名为"items"的键，其值是一个对象数组。数组中的每个对象代表一个商品，包含两个键:"item_name"(字符串)和"price"(字符串)。
            如果没有明确提到某个商品的价格，则将价格设置为"未指定"。
            如果多个价格被提及但仅仅基于提供的文本无法明确哪个价格对应哪个商品，请尽力根据上下文将它们关联起来，或者如果无法关联则分别列出。
            确保输出是一个单一的、有效的JSON对象。
            """
            
            # 构建用户提示
            user_prompt = f"""
            以下是来自论坛帖子的信息:

            标题: {title}
            价格字段: {price_field}

            内容:
            {content}

            请按照指定的JSON格式提取商品和它们的价格。
            """
            
            # 准备聊天请求
            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ]
            
            # 发送请求到LLM
            logger.debug(f"正在向 {self.model} 模型发送分析请求...")
            
            # 设置超时控制
            import time
            start_time = time.time()
            
            # 发送聊天请求到LLM，启用JSON模式，并设置超时
            try:
                # 这里我们使用client的timeout设置而不是每次请求都传递timeout参数
                # OpenAI客户端在创建时已经设置了timeout
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},  # 启用JSON输出模式
                )
                elapsed_time = time.time() - start_time
                logger.debug(f"LLM分析完成，耗时: {elapsed_time:.2f}秒")
                
                # 处理响应
                if completion.choices:
                    response_content = completion.choices[0].message.content
                    logger.debug(f"收到LLM响应: {response_content[:200]}...")
                    
                    # 处理可能存在的Markdown代码块标记
                    cleaned_content = response_content
                    if cleaned_content.startswith("```"):
                        first_line_end = cleaned_content.find("\n")
                        if first_line_end != -1:
                            cleaned_content = cleaned_content[first_line_end + 1:]
                    
                    if cleaned_content.rstrip().endswith("```"):
                        last_triple_backtick = cleaned_content.rstrip().rfind("```")
                        cleaned_content = cleaned_content[:last_triple_backtick].rstrip()
                    
                    # 解析JSON
                    try:
                        parsed_json = json.loads(cleaned_content)
                        
                        # 访问提取出的项目
                        if "items" in parsed_json and isinstance(parsed_json["items"], list):
                            items = parsed_json["items"]
                            logger.info(f"LLM成功提取出 {len(items)} 个商品信息")
                            for item in items:
                                item_name = item.get("item_name", "N/A")
                                price = item.get("price", "N/A")
                                logger.info(f"提取的商品: {item_name}, 价格: {price}")
                            return parsed_json
                        else:
                            logger.warning("LLM响应中未找到预期的'items'列表")
                            return {"items": []}
                    except json.JSONDecodeError as e:
                        logger.error(f"无法解析LLM响应为有效的JSON: {e}")
                        return {"items": []}
                else:
                    logger.warning("未收到有效的LLM响应")
                    return {"items": []}
                    
            except TimeoutError:
                logger.error(f"LLM分析请求超时，已经过{timeout}秒")
                return {"items": []}
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"LLM分析请求失败，用时{elapsed_time:.2f}秒，错误: {e}")
                return {"items": []}
                
        except Exception as e:
            logger.error(f"调用LLM分析时出错: {e}")
            return {"items": []} 