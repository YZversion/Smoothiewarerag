"""
B.3 查询压测：50 条通用 C++ 查询，测量 P50/P95/P99 检索延迟。
用法：python scripts/benchmark_queries.py
"""
import sys, time, statistics, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

QUERIES = [
    # 类定义
    "class definition constructor destructor",
    "abstract base class virtual method",
    "template class specialization",
    "class inheritance polymorphism",
    "operator overloading",
    # 函数实现
    "function implementation return value",
    "static method class function",
    "inline function header definition",
    "recursive function depth limit",
    "callback function pointer",
    # 错误处理
    "error handling exception try catch",
    "error code return value check",
    "assert failure condition",
    "null pointer check dereference",
    "buffer overflow bounds check",
    # 多线程
    "mutex lock unlock thread safety",
    "thread create join synchronization",
    "atomic operation memory order",
    "condition variable wait notify",
    "race condition critical section",
    # 宏与预处理
    "macro definition preprocessor",
    "ifdef ifndef platform conditional",
    "define constant value",
    "pragma once include guard",
    "variadic macro arguments",
    # 内存管理
    "memory allocation malloc free",
    "smart pointer unique_ptr shared_ptr",
    "RAII resource acquisition",
    "memory leak detection",
    "stack heap allocation",
    # 数据结构
    "vector array dynamic size",
    "map dictionary key value lookup",
    "linked list node pointer",
    "queue deque push pop",
    "hash table unordered_map",
    # 文件与IO
    "file read write open close",
    "stream input output buffer",
    "string parsing split trim",
    "JSON parse serialize",
    "log write message level",
    # 算法
    "sort algorithm comparison",
    "search binary linear find",
    "iterator range begin end",
    "algorithm transform filter",
    "comparison operator less greater",
    # 通用查询
    "initialize setup configuration",
    "cleanup destroy finalize",
    "event callback handler",
    "state machine transition",
    "timer interrupt signal",
]

def run_benchmark():
    from search.index import SearchIndex
    idx = SearchIndex()
    idx.load_index()
    sym_count = sum(len(v) for v in idx._SYMBOL_BY_NAME.values())
    print(f"Index loaded: {len(idx._CHUNKS)} chunks, {sym_count} symbols")
    print(f"Running {len(QUERIES)} queries...")

    latencies = []
    errors = 0

    for q in QUERIES:
        t0 = time.perf_counter()
        try:
            results = idx.search(q, top_k=8)
        except Exception as e:
            errors += 1
            results = []
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    latencies.sort()
    n = len(latencies)
    p50 = latencies[n // 2]
    p95 = latencies[int(n * 0.95)]
    p99 = latencies[int(n * 0.99)]
    avg = statistics.mean(latencies)
    mn  = latencies[0]
    mx  = latencies[-1]

    print(f"\n{'='*50}")
    print(f"Queries : {len(QUERIES)}  Errors: {errors}")
    print(f"Min     : {mn:.1f} ms")
    print(f"P50     : {p50:.1f} ms")
    print(f"P95     : {p95:.1f} ms")
    print(f"P99     : {p99:.1f} ms")
    print(f"Max     : {mx:.1f} ms")
    print(f"Avg     : {avg:.1f} ms")
    print(f"{'='*50}")

    # Pass/fail per acceptance criteria
    ok = p95 <= 500
    status = "PASS" if ok else "FAIL"
    print(f"\nP95 <= 500ms: {status} ({p95:.0f}ms)")

    return {
        "query_count": len(QUERIES),
        "errors": errors,
        "min_ms": round(mn, 1),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "p99_ms": round(p99, 1),
        "max_ms": round(mx, 1),
        "avg_ms": round(avg, 1),
        "pass_p95_500ms": ok,
    }

if __name__ == "__main__":
    result = run_benchmark()
    out = Path(__file__).parent.parent / "data" / "benchmark_latency.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved → {out}")
