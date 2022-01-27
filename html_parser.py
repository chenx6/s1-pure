from typing import NamedTuple
from re import compile as rcompile

from httpx import AsyncClient
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
}
post_id_r = rcompile(r"thread-(\d+)-\d+-\d+.html")
forum_id_r = rcompile(r"forum-(\d+)-1.html")
client = AsyncClient(headers=headers)


class PostContent(NamedTuple):
    """帖子回复内容"""

    post_id: int
    user: str
    user_id: int
    avatar: str
    content: str
    time: str


class ThreadContent(NamedTuple):
    """帖子内容"""

    title: str
    total_page: int
    forum_name: str
    forum_id: str
    posts: list[PostContent]


class ThreadEntry(NamedTuple):
    """帖子在版块中的入口点"""

    title: str
    thread_id: str


class ForumPage(NamedTuple):
    """帖子页面"""

    title: str
    total_page: int
    threads: list[ThreadEntry]


class ForumEntry(NamedTuple):
    """版块在主页的入口点"""

    title: str
    forum_id: int


def fix_content(content):
    """
    修复 Discusz 离谱的 html
    """
    # 解决 img 标签缺少 src 的问题
    imgs = content.select("img[file]")
    for img in imgs:
        img["src"] = img["file"]
    inner_content = content.select_one("td")
    # 修复渲染问题
    if inner_content:
        inner_content.name = "div"
        inner_content["class"] = "markdown-body"
        return str(inner_content)
    else:
        return str(content)


def parse_plhin(post) -> PostContent:
    """
    解析每一个回帖（.plhin）里的内容
    """
    post_id = post["id"].replace("pid", "")
    user = post.select_one(".authi > .xw1")
    user_id = user["href"].replace("space-uid-", "").replace(".html", "")
    avatar = post.select_one(".avatar > .avtm > img")
    if avatar:
        avatar = avatar["src"]
    else:
        avatar = ""
    content = post.select_one(".pcb")
    content = fix_content(content)
    time = post.select_one(".authi > em").text.replace("发表于 ", "")
    return PostContent(int(post_id), user.text, int(user_id), avatar, content, time)


async def parse_thread(thread_id: int, page_num: int = 1):
    """
    解析帖子里的内容
    """
    resp = await client.get(
        f"https://bbs.saraba1st.com/2b/thread-{thread_id}-{page_num}-1.html"
    )
    soup = BeautifulSoup(resp.text, features="html.parser")
    # with open("thread-2036367-1-1.html") as f:
    #     text = f.read()
    # soup = BeautifulSoup(text, features="html.parser")
    title = soup.select_one("#thread_subject")
    assert title
    title = title.text
    posts = soup.select(".plhin")
    posts = list(map(parse_plhin, posts))
    total_page = soup.select_one("span[title]")
    forum = soup.select_one(".z > a[href^='forum-']")
    assert forum
    if not total_page:
        total_page = "1"
    else:
        total_page = total_page.text.replace("/", "").replace("页", "")
    return ThreadContent(
        title,
        int(total_page),
        forum.text,
        forum_id_r.findall(str(forum["href"]))[0],
        posts,
    )


async def parse_forum(forum_id: int, page: int):
    """
    解析版面内容
    """
    resp = await client.get(
        f"https://bbs.saraba1st.com/2b/forum-{forum_id}-{page}.html"
    )
    soup = BeautifulSoup(resp.text, features="html.parser")
    thread_lst = soup.find_all("a", class_="s xst")
    thread_lst = list(
        map(
            lambda t: ThreadEntry(t.text, post_id_r.findall(t["href"])[0]),
            thread_lst,
        )
    )
    total_page = soup.find("a", class_="last")
    assert total_page
    total_page = total_page.text.replace("... ", "")
    title = soup.select_one(".xs2 > a")
    assert title
    title = title.text
    return ForumPage(title, int(total_page), thread_lst)


async def parse_forums():
    resp = await client.get("https://bbs.saraba1st.com/2b/forum.php")
    soup = BeautifulSoup(resp.text, features="html.parser")
    tb = soup.select_one("#category_1")
    assert tb
    dts = tb.select("dt")
    forum_entries = list(
        map(
            lambda dt: ForumEntry(
                dt.a.text, int(forum_id_r.findall(dt.a["href"])[0])  # type: ignore
            ),
            dts,
        )
    )
    return forum_entries


if __name__ == "__main__":
    from asyncio import run

    # run(parse_thread(1998862, 1))
    # run(parse_forum(6, 1))
    run(parse_forums())
