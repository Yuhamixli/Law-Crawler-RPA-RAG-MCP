#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速IP轮换工具
用于手动测试和切换代理IP
"""

import asyncio
import sys
from loguru import logger
from src.crawler.utils.enhanced_proxy_pool import EnhancedProxyPool

class IPRotator:
    """IP轮换器"""
    
    def __init__(self):
        self.proxy_pool = None
        
    async def initialize(self):
        """初始化代理池"""
        logger.info("🚀 初始化代理池...")
        self.proxy_pool = EnhancedProxyPool("config/proxy_config.toml")
        await self.proxy_pool.initialize()
        
    async def list_available_proxies(self):
        """列出所有可用代理"""
        logger.info("\n📋 可用代理列表:")
        logger.info("="*60)
        
        if not self.proxy_pool.paid_proxies:
            logger.warning("❌ 没有找到付费代理")
            return
            
        for i, proxy in enumerate(self.proxy_pool.paid_proxies, 1):
            status = "🟢" if proxy.is_alive else "🔴"
            cooldown = "❄️" if self.proxy_pool._is_in_cooldown(proxy) else "🔥"
            
            logger.info(f"{i:2d}. {status}{cooldown} {proxy.name}")
            logger.info(f"     地址: {proxy.address}:{proxy.port}")
            logger.info(f"     协议: {proxy.protocol.value}")
            logger.info(f"     成功率: {proxy.success_rate:.1%}")
            logger.info(f"     响应时间: {proxy.response_time:.2f}s")
            logger.info("")
            
    async def get_current_ip(self):
        """获取当前使用的IP"""
        proxy = await self.proxy_pool.get_proxy(prefer_paid=True)
        if proxy:
            logger.info(f"🌍 当前代理: {proxy.name} [{proxy.address}:{proxy.port}]")
            return proxy
        else:
            logger.warning("❌ 无可用代理")
            return None
            
    async def rotate_to_next_ip(self):
        """轮换到下一个IP"""
        logger.info("🔄 正在轮换IP...")
        proxy = await self.proxy_pool.get_proxy(prefer_paid=True, force_rotation=True)
        
        if proxy:
            logger.info(f"✅ 已切换到: {proxy.name} [{proxy.address}:{proxy.port}]")
            return proxy
        else:
            logger.warning("❌ 轮换失败，无可用代理")
            return None
            
    async def test_specific_region(self, region_keyword: str):
        """测试特定地区的代理"""
        logger.info(f"🌏 寻找包含 '{region_keyword}' 的代理...")
        
        matching_proxies = [
            p for p in self.proxy_pool.paid_proxies 
            if region_keyword in p.name and p.is_alive
        ]
        
        if not matching_proxies:
            logger.warning(f"❌ 没有找到包含 '{region_keyword}' 的可用代理")
            return None
            
        proxy = matching_proxies[0]
        logger.info(f"🎯 选择代理: {proxy.name} [{proxy.address}:{proxy.port}]")
        return proxy
        
    async def clear_proxy_cooldowns(self):
        """清除所有代理冷却"""
        logger.info("🧹 清除代理冷却时间...")
        
        cleared_count = len(self.proxy_pool.proxy_cooldown)
        self.proxy_pool.proxy_cooldown.clear()
        
        # 重置失败计数
        for proxy in self.proxy_pool.paid_proxies:
            proxy.failure_count = 0
            proxy.is_alive = True
            
        logger.info(f"✅ 已清除 {cleared_count} 个代理的冷却状态")
        
    async def show_stats(self):
        """显示代理池统计"""
        self.proxy_pool.print_stats()

async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("🔧 IP轮换工具使用说明:")
        print("python rotate_ip.py <命令>")
        print("\n可用命令:")
        print("  list        - 列出所有可用代理")
        print("  current     - 显示当前代理")
        print("  rotate      - 轮换到下一个IP")
        print("  stats       - 显示代理池统计")
        print("  clear       - 清除代理冷却")
        print("  test <地区>  - 测试特定地区代理 (如: test 香港)")
        print("\n示例:")
        print("  python rotate_ip.py list")
        print("  python rotate_ip.py rotate")
        print("  python rotate_ip.py test 台湾")
        return
        
    command = sys.argv[1].lower()
    
    rotator = IPRotator()
    await rotator.initialize()
    
    if command == "list":
        await rotator.list_available_proxies()
        
    elif command == "current":
        await rotator.get_current_ip()
        
    elif command == "rotate":
        await rotator.rotate_to_next_ip()
        
    elif command == "stats":
        await rotator.show_stats()
        
    elif command == "clear":
        await rotator.clear_proxy_cooldowns()
        
    elif command == "test" and len(sys.argv) >= 3:
        region = sys.argv[2]
        await rotator.test_specific_region(region)
        
    else:
        logger.error("❌ 未知命令，请使用 'python rotate_ip.py' 查看帮助")

if __name__ == "__main__":
    asyncio.run(main()) 