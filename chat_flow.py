# 添加自定义Node支持本项目API接口，本地部署langflow实现对话功能
# 当前功能还很少，主要为了演示自定义langflow节点


# 运行方式：
# 1. 安装python=3.9或3.10(推荐)，或者新建一个对应版本的虚拟环境
# 2. 安装langchain & langflow & uvicorn
# 3. 运行python chat_flow.py


# Todo：
# 1. 当前只添加了最简单的LLM节点，支持的参数也有限。
#    需要与API接口同步更新接口参数
# 2. 暂不支持流式输出
#    正在开发当中。langflow本身输出能力有限，考虑与streamlit集成
# 3. 暂不支持知识库
# 4. 结合项目实现，添加更多的自定义Node


# from langchain import PromptTemplate, OpenAI, LLMChain
from typing import *
import requests
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langflow import lcserve
from langflow.main import app
from langflow.interface import types
from langflow.interface import custom_lists
from langflow.custom import customs
from langflow.interface.llms import base
from langflow.interface.llms.base import llm_creator
from langflow.template.frontend_node.llms import LLMFrontendNode
from langflow.template.template.base import Template
from langflow.template.field.base import TemplateField


class ChatGLM(LLM):
    """ChatGLM LLM service.
        参照langchain.llms.ChatGLM修改而来
    """

    endpoint_url: str = "http://127.0.0.1:7861/chat"
    """Endpoint URL to use."""
    model_kwargs: Optional[dict] = None
    """Key word arguments to pass to the model."""
    max_token: int = 20000
    """Max token allowed to pass to the model."""
    temperature: float = 0.1
    """LLM model temperature from 0 to 10."""
    history: List[List] = []
    """History of the conversation"""
    top_p: float = 0.7
    """Top P for nucleus sampling from 0 to 1"""
    streaming: bool = False
    history_len: int = 3  # 暂时自己维护history，后面可以改用langchain memory

    @property
    def _llm_type(self) -> str:
        return "ChatGLM"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"endpoint_url": self.endpoint_url},
            **{"model_kwargs": _model_kwargs},
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        streaming: bool = False,
        **kwargs: Any,
    ) -> str:
        """Call out to a ChatGLM LLM inference endpoint.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = chatglm_llm("Who are you?")
        """
        _model_kwargs = self.model_kwargs or {}

        # HTTP headers for authorization
        headers = {"Content-Type": "application/json"}

        payload = {
            "question": prompt,
            # "prompt": prompt,
            # "temperature": self.temperature,
            "history": self.history[-self.history_len:],
            # "max_length": self.max_token,
            # "top_p": self.top_p,
            # "streaming": streaming,
        }
        # payload.update(_model_kwargs)
        # payload.update(kwargs)

        # print("ChatGLM payload:", payload)
        if streaming:
            return 'streaming not work yet'
            try:
                response = requests.post(
                    self.endpoint_url,
                    json=payload,
                    stream=True,
                )

            except requests.exceptions.RequestException as e:
                raise ValueError(f"Error raised by inference endpoint: {e}")

            if response.status_code != 200:
                raise ValueError(f"Failed with response: {response}")

            # for x in response.iter_content(None):
            #     yield x.decode() 

        else:
            try:
                response = requests.post(
                    self.endpoint_url, headers=headers, json=payload)
            except requests.exceptions.RequestException as e:
                raise ValueError(f"Error raised by inference endpoint: {e}")

            # print("ChatGLM resp:", response)

            if response.status_code != 200:
                raise ValueError(f"Failed with response: {response}")

            try:
                parsed_response = response.json()

                # Check if response content does exists
                if isinstance(parsed_response, dict):
                    content_keys = "response"
                    if content_keys in parsed_response:
                        text = parsed_response[content_keys]
                    else:
                        raise ValueError(f"No content in response : {parsed_response}")
                else:
                    raise ValueError(f"Unexpected response type: {parsed_response}")

            except requests.exceptions.JSONDecodeError as e:
                raise ValueError(
                    f"Error raised during decoding response from inference endpoint: {e}."
                    f"\nResponse: {response.text}"
                )

            if stop is not None:
                text = enforce_stop_tokens(text, stop)
            self.history = self.history + [[None, parsed_response["response"]]]
            return text

    # async def acall(
    #     self,
    #     prompt: str,
    #     stop: Optional[List[str]] = None,
    #     run_manager: Optional[CallbackManagerForLLMRun] = None,
    #     streaming: bool = False,
    #     **kwargs: Any,
    # ) -> str:
    #     breakpoint()
    #     return self._call(prompt,stop,run_manager,streaming,**kwargs)


# 配置langflow运行环境
path = Path(lcserve.__file__).parent
static_files_dir = path / "frontend"
app.mount(
    "/",
    StaticFiles(directory=static_files_dir, html=True),
    name="static",
)


# 当前是直接把Node以json的形式写到types.langchain_types_dict
# 后续考虑使用自定义Node来实现
# class ChatGLMNode(LLMFrontendNode):
#     name = 'ChatGLM'
#     description = 'chatglm llm'
#     base_classes: List[str] = ['ChatGLM', 'BaseLLM', 'BaseLanguageModel']
#     template = Template(
#         type_name='ChatGLM',
#         fields=[
#             TemplateField(
#                 name='question'
#             )
#         ]
#     )
# customs.CUSTOM_NODES.setdefault('llms', {})
# customs.CUSTOM_NODES['llms'].update(
#     ChatGLM = ChatGLMNode(),
# )


# 把自定义模式加入到langflow数据结构中
custom_lists.CUSTOM_NODES.update(
    ChatGLM=ChatGLM,
)

types.langchain_types_dict['llms']['ChatGLM'] = {
    'name': 'ChatGLM',
    'display_name': 'ChatGLM',
    'template': {
        'endpoint_url': TemplateField(
            name='endpoint_url',
            value='http://127.0.0.1:7861/chat',
        ).to_dict(),
        'prompt': TemplateField(
            name='prompt',
            value='hello',
        ).to_dict(),
        'streaming': TemplateField(
            name='streaming',
            display_name='streaming',
            value=False,
            field_type='bool',
        ).to_dict(),
        '_type': 'ChatGLM',
    },
    'base_classes': ['ChatGLM', 'BaseLLM', 'BaseLanguageModel'],
    'description': 'chatglm llm',
    'documentation': '',
}
base.llm_type_to_cls_dict['ChatGLM'] = ChatGLM
llm_creator.type_dict['ChatGLM'] = ChatGLM


# llms = types.langchain_types_dict['llms']
# types.langchain_types_dict = types.build_langchain_types_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)