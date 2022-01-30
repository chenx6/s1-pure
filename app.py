from typing import Callable
from starlette.applications import Starlette
from starlette.templating import Jinja2Templates
from starlette.routing import Route
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from httpx import TimeoutException
from cacheout import Cache

from html_parser import parse_forum, parse_forums, parse_thread

templates = Jinja2Templates("./templates")
cache = Cache()


class CustomErrorMiddleware(BaseHTTPMiddleware):
    """全局错误处理"""

    @staticmethod
    def error_response(request, exception, status_code: int = 400):
        """错误页面模板渲染"""
        return templates.TemplateResponse(
            "error.html", {"request": request, "exception": exception}, status_code
        )

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except TimeoutException:
            return self.error_response(request, "请求超时了")
        except AssertionError:
            return self.error_response(request, "HTML 解析出错了")
        except Exception as e:
            return self.error_response(request, str(e))


async def is_cached(request: Request, or_do: Callable, ttl: int = 60):
    """查看请求页面是否被缓存，如果没有缓存就调取抓取数据函数再缓存"""
    url = str(request.url)
    result = cache.get(url)
    if not result:
        result = await or_do()
        cache.set(url, result, ttl)
    return result


async def get_thread(request: Request):
    """获取并渲染，返回单个帖子内容"""
    thread_id = request.path_params.get("thread_id", 1)
    page = request.query_params.get("page", 1)
    page = int(page)
    result = await is_cached(request, lambda: parse_thread(thread_id, page))
    return templates.TemplateResponse(
        "thread.html",
        {
            "request": request,
            "result": result,
            "origin_url": f"https://bbs.saraba1st.com/2b/thread-{thread_id}-{page}-1.html",
            "curr_page": page,
            "next_page": page + 1,
            "previous_page": page - 1,
        },
    )


async def get_forum(request: Request):
    """获取并渲染，返回单个版块内容"""
    forum_id = request.path_params.get("forum_id", 1)
    page = request.query_params.get("page", 1)
    page = int(page)
    result = await is_cached(request, lambda: parse_forum(forum_id, page))
    return templates.TemplateResponse(
        "forum.html",
        {
            "request": request,
            "result": result,
            "origin_url": f"https://bbs.saraba1st.com/2b/forum-{forum_id}-{page}.html",
            "curr_page": page,
        },
    )


async def get_forums(request: Request):
    """获取并渲染，返回主页内容"""
    result = await is_cached(request, lambda: parse_forums())
    return templates.TemplateResponse(
        "forums.html",
        {
            "request": request,
            "forums": result,
            "origin_url": "https://bbs.saraba1st.com/2b/forum.php",
        },
    )


routes = [
    Route("/thread/{thread_id:int}", get_thread),
    Route("/forum/{forum_id:int}", get_forum),
    Route("/forums", get_forums),
]
middlewares = [Middleware(CustomErrorMiddleware)]
app = Starlette(routes=routes, middleware=middlewares)
