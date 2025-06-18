"""
测试已知存在的法律
"""
import asyncio
from src.crawler.strategies.npc_api_crawler import NPCAPICrawler
from loguru import logger
import json


async def test_known_laws():
    """测试一些已知存在的法律"""
    
    # 这些是从主页看到的法律
    known_laws = [
        "中华人民共和国监察法",
        "中华人民共和国增值税法",
        "中华人民共和国科学技术普及法",
        "中华人民共和国学前教育法",
        "监察法",  # 尝试简称
        "增值税法",
        "宪法"  # 测试宪法
    ]
    
    async with NPCAPICrawler() as crawler:
        for law_name in known_laws:
            logger.info(f"\n=== 搜索: {law_name} ===")
            
            results = await crawler.search(law_name)
            
            if results:
                logger.success(f"找到 {len(results)} 条结果")
                for i, result in enumerate(results[:3]):
                    logger.info(f"{i+1}. {result['name']} - {result.get('law_type', 'N/A')}")
                    
                # 尝试获取第一个结果的详情
                if results:
                    first_result = results[0]
                    logger.info(f"\n获取详情: {first_result['name']}")
                    
                    detail = await crawler.get_detail(first_result['id'])
                    if detail:
                        logger.info(f"详情获取成功!")
                        logger.info(f"  - 名称: {detail.get('name')}")
                        logger.info(f"  - 类型: {detail.get('law_type')}")
                        logger.info(f"  - 发布日期: {detail.get('publish_date')}")
                        logger.info(f"  - 生效日期: {detail.get('effective_date')}")
                        
                        # 保存一个示例
                        if law_name == "监察法":
                            with open("data/test_laws/监察法_detail.json", 'w', encoding='utf-8') as f:
                                json.dump(detail, f, ensure_ascii=False, indent=2)
            else:
                logger.warning(f"未找到: {law_name}")
                
            await asyncio.sleep(1)


if __name__ == "__main__":
    # 设置日志级别为DEBUG以查看详细信息
    logger.remove()
    logger.add(lambda msg: print(msg), level="DEBUG")
    
    asyncio.run(test_known_laws()) 