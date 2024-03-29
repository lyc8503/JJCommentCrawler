import time
import bs4
import requests
import re
import logging
import sqlite3
import html2text
logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    level=logging.INFO)

id = int(input("请输入 NovelID(可在晋江网页端地址中找到): "))

# 连接数据库
conn = sqlite3.connect('comments_' + str(id) + '.db')
cursor = conn.cursor()
cursor.execute('create table comments (id varchar(1024) primary key, content varchar(409600));')
conn.commit()


def get_one_chapter_all(cid, cookies):
    global cursor, conn
    try:
        for i in range(1, 10000000):
            # 获取页面内容
            for i2 in range(0, 3):
                try:
                    r = None
                    logging.info("正在获取第" + str(i) + "页评论...")
                    # 尝试获取页面
                    while True:
                        try:
                            time.sleep(3)
                            r = requests.get("https://www.jjwxc.net/comment.php", params={
                                "novelid": id,
                                "chapterid": cid,
                                "page": i,
                                # 如果只想要获取长评取消注释下面这行
                                # "wonderful": 1
                                # 如果只想要获取作者加精评论取消注释下面这行
                                # "belike": 1
                                # 如果只想要获取话题取消注释下面这行
                                # "huati": 1

                                # 以上三行可以自行注释或取消注释, 但一次最多取消注释一行
                                # 默认全部注释即获取所有评论
                            }, verify=False, timeout=15, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                                "Cookie": cookies
                            })
                            break
                        except Exception as e:
                            logging.warning("网络连接出错: " + str(e))

                    # 使用 bs4 解析数据
                    soup = bs4.BeautifulSoup(r.content.decode("gbk", errors='ignore'), features="lxml")

                    # 使用正则匹配评论 div
                    comment_selector = re.compile("comment_[0-9]*")
                    comments = soup.find_all('div', id=comment_selector)

                    logging.info("成功抓取到" + str(len(comments)) + "条评论.")

                    if len(comments) == 0:
                        raise Exception("没有更多数据.(数据抓取完成? ip 被封? Cookie 失效?)")

                    break
                except Exception as e:
                    logging.warning("第" + str(i) + "页未获取到内容, 30s后重试")
                    time.sleep(30)
            else:
                raise Exception("连续3次重试未获取到内容.")

            # 解析保存评论
            for c in comments:
                t = None
                try:
                    logging.debug("获取的评论ID: " + c['id'][8:])
                    t = html2text.html2text(str(c))

                    time_re = re.compile("发表时间：[0-9\-\s:]*")
                    name_re = re.compile("网友：\[[\s\S]*?\]")

                    # 用评论者的发表时间和名字作为 id 应该会唯一吧
                    c_time = (time_re.findall(t)[0][5:]).replace("\n", "-").strip()
                    try:
                        c_name = name_re.findall(t)[0][3:].replace("\n", "-").strip()
                    except IndexError as e:
                        if "[作者评论]" in t:
                            c_name = "[作者评论]"
                        else:
                            # 很久以前的一些评论可能网友名字没有链接, 用上面的正则匹配不到...
                            c_name = re.compile("网友：[\S]*").findall(t)[0][3:].replace("\n", "-").strip()

                    uid = c_time + "_" + c_name

                    cursor.execute('insert into comments (id, content) values (?, ?)',
                                   (uid + "_" + str(cid), t))
                    conn.commit()

                    logging.debug("评论 " + uid + " 保存成功.")
                except sqlite3.IntegrityError as e:
                    logging.warning("评论保存失败. 可能是同一用户在1s内发送了两条评论或从晋江获取到的内容重复.")
                except IndexError as e:
                    logging.warning("评论保存失败. 正则匹配出错: " + t)

    except Exception as e:
        logging.warning("本章节获取结束: " + str(e))
        conn.commit()
        raise e


ran = input("输入章节数范围(示例: 1-100), 代表获取 1-100 章的评论: ")
cookies = input("如果需要 VIP 章节, 请输入 Cookie, 否则留空: ")

for i in range(int(ran.split('-')[0]), int(ran.split('-')[1]) + 1):
    logging.info("------ 第 " + str(i) + " 章 ------")
    try:
        get_one_chapter_all(i, cookies)
    except Exception as e:
        logging.error(e)

logging.info("全部完成.")
conn.commit()
cursor.close()
conn.close()
