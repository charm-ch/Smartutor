#!/bin/bash
# M1 检索质量抽检 v2：按完整内容判定命中（部署 content 修复后）
set -e
cd /opt/zhixue/backend
KB=$(cat /tmp/e2e_kbid.txt | cut -d= -f2)
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python <<PYEOF
import asyncio, sys
sys.path.insert(0, '.')

QUESTIONS = [
    ("什么是空指针？解引用会怎样？", ["空指针", "段错误"]),
    ("野指针是什么？", ["野指针"]),
    ("悬空指针怎么产生？", ["悬空指针", "dangling"]),
    ("数组下标越界会怎么样？", ["越界", "边界"]),
    ("怎么计算数组元素个数？", ["sizeof"]),
    ("二维数组怎么定义？", ["二维数组", "matrix"]),
    ("for循环死循环的常见原因？", ["更新", "死循环"]),
    ("break和continue的区别？", ["break 立即终止", "continue"]),
    ("怎么调试死循环？", ["gdb", "CPU 占用"]),
    ("函数参数是值传递还是引用传递？", ["值传递", "pass by value"]),
    ("递归必须有终止条件吗？", ["终止条件", "base case"]),
    ("返回局部变量的地址有什么问题？", ["局部变量", "栈"]),
    ("malloc失败返回什么？", ["malloc", "NULL"]),
    ("内存泄漏是什么？", ["内存泄漏", "free"]),
    ("double free会怎样？", ["重复释放", "double free"]),
    ("怎么检测内存泄漏？", ["valgrind", "AddressSanitizer"]),
    ("strlen和sizeof的区别？", ["strlen", "sizeof"]),
    ("字符串常量能修改吗？", ["只读", "字符串常量"]),
    ("结构体指针怎么访问成员？", ["箭头", "->"]),
    ("fopen失败返回什么？", ["fopen", "NULL"]),
]

async def main():
    from app.services import rag
    hit, total = 0, len(QUESTIONS)
    for q, keywords in QUESTIONS:
        chunks = await rag.retrieve("$KB", q, top_k=5)
        # 命中判定：Top-5 任一块的完整内容包含关键词
        found = any(
            any(kw.lower() in c.get("content", c["snippet"]).lower() for kw in keywords)
            for c in chunks
        )
        if found:
            hit += 1
        print(f"[{'HIT ' if found else 'MISS'}] {q}")
    rate = hit / total * 100
    print(f"\n===== 命中率(全文口径): {hit}/{total} = {rate:.0f}% （验收标准 ≥80%）=====")

asyncio.run(main())
PYEOF
