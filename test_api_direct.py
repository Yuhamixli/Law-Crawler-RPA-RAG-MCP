"""
直接测试国家法律法规数据库API
"""
import httpx
import asyncio
import json
from loguru import logger


async def test_api():
    """测试API"""
    
    # 测试不同的参数组合
    test_cases = [
        {
            "name": "简单搜索",
            "params": {
                "keyword": "反洗钱"
            }
        },
        {
            "name": "完整参数搜索",
            "params": {
                "keyword": "反洗钱法",
                "type": "title",
                "searchType": "title",
                "sortTr": "f_bbrq_s",
                "page": 1,
                "size": 10,
                "showDetailLink": 1,
                "checkFlag": 1
            }
        },
        {
            "name": "最小参数搜索",
            "params": {
                "keyword": "统计法",
                "page": 1,
                "size": 10
            }
        }
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://flk.npc.gov.cn/"
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        for test in test_cases:
            logger.info(f"\n=== {test['name']} ===")
            
            try:
                # GET请求
                response = await client.get(
                    "https://flk.npc.gov.cn/api/search",
                    params=test["params"],
                    headers=headers
                )
                
                logger.info(f"状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.success("API调用成功!")
                    
                    if data.get("result") and data["result"].get("data"):
                        results = data["result"]["data"]
                        logger.info(f"找到 {len(results)} 条结果:")
                        
                        for i, item in enumerate(results[:3]):  # 只显示前3条
                            logger.info(f"  {i+1}. {item.get('title')} ({item.get('type')})")
                    else:
                        logger.warning("未找到结果")
                else:
                    logger.error(f"API返回错误: {response.text[:200]}")
                    
            except Exception as e:
                logger.error(f"请求失败: {str(e)}")
                
            await asyncio.sleep(2)
            
    # 测试已知的法律ID
    logger.info("\n=== 测试获取详情 ===")
    
    test_ids = [
        "ZmY4MDgxODE5NDQwNjk3MjAxOTQ5NjBkY2VhMzQ1YTI%3D",  # 监察法
        "ZmY4MDgxODE5MjdiMDgzYjAxOTNmZDY1YTBlYjAyY2I%3D"   # 增值税法
    ]
    
    async with httpx.AsyncClient(timeout=30) as client:
        for law_id in test_ids:
            try:
                # 尝试detail API
                response = await client.get(
                    "https://flk.npc.gov.cn/api/detail",
                    params={"id": law_id},
                    headers=headers
                )
                
                logger.info(f"详情API状态码: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"响应内容: {response.text[:200]}")
                    
            except Exception as e:
                logger.error(f"详情请求失败: {str(e)}")
                
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(test_api()) 