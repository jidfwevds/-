import requests

GLM_API_KEY = "fb2d45b7966f47f1ac8da3a9046e7bca.jotkQoRPfia1ZGEC"  # 建议移到环境变量
GLM_MODEL = "glm-4.6v-flash"
GLM_MAX_TOKENS = 1000
GLM_TIMEOUT = 30  # 请求超时时间

class GLM_Vision_API:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def describe_image_base64(self, image_base64,
                              prompt="请详细描述这张图片中的内容，包括人物、场景、动作、氛围等"):
        """直接接收Base64编码的图片进行描述"""
        try:
            # 构造请求数据（遵循智谱官方格式）
            data = {
                "model": GLM_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                "max_tokens": GLM_MAX_TOKENS
            }

            # 发送请求
            response = requests.post(
                self.url,
                headers=self.headers,
                json=data,
                timeout=GLM_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()

            # 提取回复内容
            if "choices" in result and len(result["choices"]) > 0:
                description = result['choices'][0]['message']['content']
                return {
                    "success": True,
                    "description": description,
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "description": "",
                    "error": "API返回格式异常"
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "description": "",
                "error": "请求超时，请重试"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "description": "",
                "error": f"API调用失败: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "description": "",
                "error": f"处理失败: {str(e)}"
            }
