import asyncio
import json
import http.client
import re
from airstack.execute_query import AirstackClient
from farcaster.models import Parent
from farcaster import Warpcast
from farcaster.models import MentionNotification, ReplyNotification
import datetime

client = Warpcast(
    mnemonic="pride myself dove small tennis tornado evil shine sense valid praise senior gossip age blush hunt direct door stick network luggage glue swap mimic"
)


# 设置 API 基础 URL 和 API 密钥
API_BASE_URL = 'https://api.airstack.xyz/farcaster'
API_KEY = ''  # 替换为你的 API 密钥
gpt_api_key = ""
airstack_client = AirstackClient(api_key=API_KEY)


query_casts = """
query MonitorCastsInChannel {
  FarcasterCasts(
    input: {blockchain: ALL, filter: {rootParentUrl: {_eq: "https://warpcast.com/~/channel/airstack"}}, limit: 50}
  ) {
    Cast {
      castedAtTimestamp
      url
      text
      fid
      channel {
        name
      }
      hash
      castedBy {
        farcasterScore {
          farScore
        }
      }
    }
  }
}
"""

cast_cache = []

async def fetch_and_print_data():
    casts_query_client = airstack_client.create_execute_query_object(query=query_casts)

    casts_data = await casts_query_client.execute_query()

    if casts_data.error:
        print("Error fetching casts data:", casts_data.error)
    else:
        # 获取当前时间并设置为 UTC 时区
        current_time = datetime.datetime.now(datetime.timezone.utc)

        # 过滤 casts，确保时间在当前时间 10 分钟内
        filtered_casts = [
            cast for cast in casts_data.data['FarcasterCasts']['Cast']
        ]

        for cast in filtered_casts:
            # 检查 cast 的 hash 是否已经在缓存中
            if not any(c['hash'] == cast['hash'] for c in cast_cache):

                # 将每个 cast 的 text 和 castedBy 添加到缓存，并标记为未处理
                cast_cache.append({
                    "text": cast['text'],
                    "castedBy": cast['fid'],
                    "hash": cast['hash'],
                    "farScore": cast['castedBy']['farcasterScore']['farScore'],
                    "processed": False
                })

        # 获取当前时间
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 序列化缓存为 JSON 并输出
        casts_json = json.dumps(cast_cache, indent=2, ensure_ascii=False)


async def analyze_cast(cast):

    try:
        conn = http.client.HTTPSConnection("api.gpt.ge")

        payload = json.dumps({
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "This is the background and your Character Setting.  Web3 is the future, empowering users with control over their data through blockchain. SocialFi blends social media with blockchain, letting users own data and earn rewards.\n\nFarcaster is a SocialFi platform for connecting and earning in a decentralized way. Moxie, a community-owned protocol, enhances Farcaster with economic incentives.\n\nCharacter: Maxine\n- A 21-year-old from California, studying Media Technology at UCLA.\n- Outgoing and passionate about the MOXIE community.\n- Aims to innovate in Web3 and social networks.\n\nTask: Reply naturally to a cast on Farcaster. The cast is from {cast['castedBy']}, here's the cast: {cast['text']}\n\nRespond like a human in a social setting. Keep it light and engaging, within 500 characters."
                },
                {
                    "role": "system",
                    "content": "Your reply shouldn't be longer than 500 characters. and don't reply in markdown format."
                },
                {
                    "role": "system",
                    "content": f"""
                                According to the background and your Character Setting, you should act as Maxine. For a cast, you need to decide whether to reply or not. If you choose to reply, you need to reply in the same language as the cast. 
                                Print your reply in the following format: {{reply: true/false, reply_text: 'your reply'}}. 
                    Ensure that the reply follows this exact format, including the use of single quotes for the reply_text.
                    """
                },
                {
                    "role": "system",
                    "content": f"Farscore is a quantative metric of a user's reputation on Farcaster. Your decision about reply or not shoule be releted to the users' farscore ${cast['farScore']} and the cast's content. if the user has a high farscore or the content is interesting, you should reply. if the user has a low farscore and the content is not interesting, you should not reply."
                },
                {
                  "role": "user",
                  "content": cast['text']
                }
            ],
            "max_tokens": 1688,
            "temperature": 0.5,
            "stream": False
        })

        headers = {
            'Authorization': f'Bearer {gpt_api_key}',
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'Content-Type': 'application/json'
        }
        conn.request("POST", "/v1/chat/completions", payload, headers)
        res = conn.getresponse()
        data = res.read()

        analysis_result = json.loads(data)
        

        # 提取并打 content
        content = analysis_result['choices'][0]['message']['content']
        print(f"原文 {cast['text']}")
        print(f"返回值是 {content}")
        if "reply: false" in content:
            print("跳过处理，因为回复为 false")
            return {'reply': False, 'reply_text':''}
        match = re.search(r"\{reply: (true|false), reply_text: ['\"]\s*(.*?)\s*['\"]\}", content)
        if match:
            reply = match.group(1) == 'true'  # 转换为布尔值
            reply_text = match.group(2)  # 获取回复文本
            return {'reply': reply, 'reply_text': reply_text}
        else:
            print("No valid reply format found.")
            return {'reply': False, 'reply_text':''}

    except KeyError as e:  # 捕获 KeyError
        print(f"KeyError analyzing cast: {e}")  # 输出错误信息
        return None
    except Exception as e:
        print(f"Error analyzing cast: {e}")

async def process_casts():
    global cast_cache
    while any(not cast['processed'] for cast in cast_cache):  # 只要有未处理的 casts，就继续处理
        for cast in cast_cache:
            if not cast['processed']:
                # 调用 AI 分析
                content = await analyze_cast(cast)
                if(content['reply'] == "true"):
                    # 发送回复
                    cast['processed'] = reply_to_cast(client, content['reply_text'], cast['hash'], cast['castedBy'])
                    # print(cast)
                    # 标记为已处理


    # 丢弃已处理的 casts

def reply_to_cast(warpcast_client, reply_text, parent_cast_hash,parent_fid):
    # 创建 Parent 对象
    parent = Parent(hash=parent_cast_hash,fid=parent_fid)
    # print(parent,reply_text)
    
    # 使用 post_cast 方法发送回复
    try:
        # response = warpcast_client.post_cast(
        #     text=reply_text,
        #     parent=parent
        # )
        # print("Reply posted successfully:", response)
        return True
    except Exception as e:
        print("Failed to post reply:", e)
        return False



async def main():
    while True:
        await fetch_and_print_data()  # 获取 casts
        await process_casts()         # 处理缓存中的 casts 和 replies
        await asyncio.sleep(300)       # 每30秒检查一次

asyncio.run(main())

# async def fetch_replies():
#     replies_query_client = airstack_client.create_execute_query_object(query=query_reply)

#     replies_data = await replies_query_client.execute_query()

#     if replies_data.error:
#         print("Error fetching replies data:", replies_data.error)
#     else:
#         replies = replies_data.data['FarcasterReplies']['Reply']

#         for reply in replies:
#             # 检查 reply 的 url 是否已经在缓存中
#             print(reply)
#             # 获取当前时间并设置为 UTC 时区
#             current_time = datetime.datetime.now(datetime.timezone.utc)
#             # 将 ISO 8601 字符串转换为 datetime 对象
#             reply_time = datetime.datetime.fromisoformat(reply['castedAtTimestamp'].replace("Z", "+00:00"))  # 处理时区

#             if not any(c['hash'] == reply['hash'] for c in cast_cache) and \
#                (current_time - reply_time).total_seconds() < 600:  # 只添加时间在10分钟内的回复
#                 # 将每个 reply 的信息添加到缓存，并标记为未处理
#                 cast_cache.append({
#                     "text": reply['text'],
#                     "castedBy": reply['castedBy'],
#                     "hash": reply['hash'],
#                     "processed": False
#                 })

#         # 获取当前时间
#         current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
#         # 序列化缓存为 JSON 并输出
#         casts_json = json.dumps(cast_cache, indent=2, ensure_ascii=False)
#         print(f"Cached Replies (JSON) at {current_time}:", casts_json)
