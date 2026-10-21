# GPU 显存约束调度

这是一份 GPU 显存约束调度的公开实现。所有实例使用同一组构造、候选搜索和无损加速规则。

## 题目与目标

每个推理请求包含输入长度 `Lin`、输出长度 `Lout` 和到达时间 `A`。调度器要给出开始时间 `S` 与 GPU 编号，同时满足：

- `S > A`；
- 单张 GPU 的并发请求数不超过 `B`；
- 任意时刻的总显存占用不超过该 GPU 的容量；
- 尽量降低总等待时间、最长完成时间和最大等待时间。

## 主要模块

源码是一个 C++17 单文件交互式程序，核心由七部分组成：

1. 在完成事件和新请求结束点上做精确显存检查；
2. 用到达事件与完成事件驱动在线/离线构造；
3. 统一尝试少量优先级权重、`earlyStop` 和 GPU 选择方式；
4. 用等待反馈（regret）生成更好的初始顺序；
5. 只接受严格改进的局部搜索，并用后缀检查点减少重算；
6. 用 `int16`、分离数组（SoA）和候选掩码做无损预筛，最终放置仍走完整检查；
7. 首帧全量到达时直接离线求解，流式输入则在全部到齐后重解尚未启动的部分。

详细推导和伪代码见 [算法说明](docs/GPU显存约束调度_算法说明.md)。

说明文档包含 11 张可缩放矢量图。曲线、权重网格、预算阶梯和候选区域均由 Python 脚本按题面公式与源码常量生成，仅用于说明算法结构，不代表运行性能。

## 编译

推荐 Linux 和支持 C++17 的 GCC：

```bash
g++ -std=c++17 -O2 -pipe src/Solution.cpp -o solution
```

程序使用 `bits/stdc++.h`、`unistd.h` 和 GCC 函数属性。x86 机器支持 AVX2 时会自动使用向量化预筛，否则使用等价的标量实现。

## 运行

程序遵循原题交互协议：每个时间步读入新到达请求，输出本轮已经确定的调度决策，并立即刷新输出。它不是一次读完整文件再统一打印答案的普通离线程序；本地运行需要配套交互器。

## 复现说明

- 源码：[src/Solution.cpp](src/Solution.cpp)
- 图表脚本：[tools/generate_figures.py](tools/generate_figures.py)
- 源码行数：1415
- SHA-256：`24f686aa7d9970e57edba770842537fc7063885ab39210aa731c052294ef2299`

安装 NumPy 与 Matplotlib 后，可以重新生成全部 SVG：

```bash
python3 tools/generate_figures.py
```

搜索受墙钟截止控制。更换 CPU、编译器或系统负载以后，可运行的候选数量可能变化，最终结果也可能略有差异。候选定义固定，实际执行子集只由算法阶段和墙钟预算决定；迁移到新机器时通常只需重新核定时间预算。

## 许可证

代码和文档采用 MIT License，见 [LICENSE](LICENSE)。

## 系列题解

[返回个人参赛题解总目录](https://github.com/XJU-ICTHUB/Huawei-Algorithm-Challenge)

- 第38期：本仓库MemWeave，[论坛题解](https://bbs.huaweicloud.com/forum/thread-02127222761354471267-1-1.html)。
- 第39期：[SlotWeave](https://github.com/XJU-ICTHUB/SlotWeave)，固定时隙均衡算法；[算法说明](https://github.com/XJU-ICTHUB/SlotWeave/blob/main/docs/solution.md)、[论坛题解](https://bbs.huaweicloud.com/forum/thread-02127227933062879438-1-1.html)。
