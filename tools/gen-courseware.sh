#!/bin/bash
# 生成增强版测试课件（多章节丰富内容 → 多块）+ 上传解析
set -e
cd /opt/zhixue/backend
BASE=http://127.0.0.1:8000

echo "=== 1. 生成增强课件（8章，每章约900字）==="
.venv/bin/python <<'PYEOF'
import fitz

chapters = {
    "第1章-指针基础": """指针（pointer）是C语言的核心概念，是一个存储内存地址的变量。
指针的定义语法为：类型 *指针名；例如 int *p; 定义了指向 int 类型的指针。
取地址运算符 & 用于获取变量地址：int a=10; int *p=&a; 此时 p 存储 a 的地址。
解引用运算符 * 用于访问指针指向的值：*p 的值为 10。
空指针 NULL：当指针不指向任何有效对象时，应初始化为 NULL，即 int *p=NULL。
解引用空指针会导致段错误（Segmentation Fault），这是初学者最常见的运行时错误。
野指针：未初始化的指针，其值是随机的，使用野指针会导致不可预测的行为。
悬空指针（dangling pointer）：指向已被释放内存的指针，free 之后应将指针置为 NULL。
指针与 const：const int *p 表示指向常量的指针，int * const p 表示指针本身是常量。
二级指针：指向指针的指针，int **pp=&p; 常用于动态数组和函数传参。""",

    "第2章-数组与越界": """数组是相同类型元素的连续存储结构。定义：int a[5]; 合法下标是 0 到 4。
C语言不进行数组边界检查，a[10]=1 属于越界写入，可能破坏相邻内存并触发段错误。
数组越界是未定义行为（Undefined Behavior），可能不立即崩溃但会埋下隐患。
数组名在表达式中会退化为指向首元素的指针，因此 a 等价于 &a[0]。
数组作为函数参数时退化为指针，sizeof 无法在函数内获得数组真实长度，需额外传长度参数 n。
遍历数组的推荐写法：for(int i=0;i<n;i++)，注意边界是小于 n 而不是小于等于 n。
静态数组元素个数计算：sizeof(a)/sizeof(a[0])。
二维数组定义：int matrix[3][4]; 表示3行4列，按行优先顺序连续存储。
字符数组与字符串：char s[]="hello"; 编译器自动在末尾添加结束符 '\\0'。
使用 strcpy 或 strcat 时必须确保目标数组足够大，否则缓冲区溢出。""",

    "第3章-循环与死循环": """C语言有三种循环结构：for 循环、while 循环和 do-while 循环。
for 循环三要素：初始化（如 int i=0）、条件（如 i<n）、更新（如 i++），用分号分隔。
缺少更新步骤是死循环的最常见原因，例如 for(int i=0;i<n;) 中忘记 i++。
while(1) 和 for(;;) 都表示无限循环，必须配合 break 或 return 退出。
do-while 循环先执行循环体再判断条件，至少执行一次，注意末尾有分号。
break 立即终止当前循环；continue 跳过本次循环体剩余部分，进入下一次条件判断。
嵌套循环中 break 只能跳出一层，需要用标志变量或 goto 跳出多层。
死循环的调试方法：观察 CPU 占用率飙升，用 gdb attach 附加进程，或 printf 打印循环变量。
循环体内修改变量时注意浮点数精度问题，如 for(float x=0;x!=1;x+=0.1) 可能永不结束。
常见笔试题：计算 1 到 100 的和，用 for 循环累加变量 s 即可。""",

    "第4章-函数与传参": """C语言函数参数是值传递（pass by value），修改形参不影响实参。
要在函数内修改外部变量，必须传递指针：void swap(int *x,int *y) 交换两个整数。
函数原型声明应放在调用之前，或统一写在头文件中：int add(int a,int b);
函数定义包含返回类型、函数名、参数列表和函数体四个部分。
递归函数必须有终止条件（base case），否则会导致栈溢出（stack overflow）。
经典递归例子：阶乘 fact(n)=n*fact(n-1)，终止条件是 n<=1 时返回 1。
递归深度过大时效率低且可能栈溢出，可改用迭代（循环）实现。
局部变量存放在栈区，函数返回后失效；返回局部变量的地址是严重错误。
static 局部变量在函数多次调用间保持值，只初始化一次。
数组作为参数传递时自动退化为指针，无法用 sizeof 求长度。""",

    "第5章-内存管理": """C语言动态内存管理依赖 stdlib.h 中的四个函数。
malloc(size) 分配指定字节数的内存，不初始化，失败返回 NULL，使用前必须判空。
calloc(n,size) 分配 n 个 size 字节的内存并清零。
realloc(ptr,newsize) 调整已分配内存的大小，可能移动内存块并返回新地址。
free(ptr) 释放动态内存，释放后应将指针置为 NULL 防止悬空指针。
内存泄漏：申请的内存忘记 free，程序运行越久占用越多，长期运行的服务必须避免。
重复释放（double free）同一块内存会导致崩溃或未定义行为。
内存分区：代码区、全局/静态区、栈区（局部变量）、堆区（动态内存）。
栈内存由编译器自动管理，函数返回自动回收；堆内存由程序员手动管理。
使用 valgrind 或 AddressSanitizer 可以检测内存泄漏和越界访问。""",

    "第6章-字符串处理": """C字符串是以 '\\0' 结尾的字符数组，存储在字符数组或动态内存中。
strlen 计算字符串长度（不含结束符）；sizeof 计算数组总大小（含结束符与未用空间）。
strcpy(dest,src) 复制字符串，必须保证 dest 空间足够，否则缓冲区溢出。
strncpy 是更安全的版本，但注意它可能不自动添加 '\\0'。
strcat 追加字符串；strcmp 按字典序比较，返回 0 表示相等。
字符串常量存储在只读区，修改字符串常量（如 char *s="hi"; s[0]='H';）会段错误。
字符数组 char s[]="hi"; 内容可修改，因为它是数组的一份拷贝。
getline/gets 读入字符串：gets 无边界检查已被废弃，应使用 fgets 并处理换行符。
sprintf 格式化到字符串，同样注意目标缓冲区大小，推荐 snprintf。
遍历字符串：while(s[i]!='\\0') 或 for(int i=0;s[i];i++)。""",

    "第7章-结构体": """结构体（struct）把多个不同类型的变量组合成一个自定义类型。
定义：struct Student { int id; char name[32]; float score; };
声明变量：struct Student stu1={1001,"张三",95.5};
点运算符访问成员：stu1.id；箭头运算符用于结构体指针：p->id 等价于 (*p).id。
结构体赋值会逐成员拷贝（浅拷贝），含指针成员时需注意深拷贝问题。
结构体作为函数参数传递的是拷贝，大结构体建议传指针以节省开销。
typedef 简化类型名：typedef struct Student Student; 之后可直接写 Student stu。
结构体大小涉及内存对齐，用 sizeof(struct Student) 获取，可能与成员大小之和不同。
结构体数组：Student class[30]; 可用循环批量处理。
链表节点常用结构体实现：struct Node { int data; struct Node *next; }。
联合体（union）所有成员共享同一块内存，大小等于最大成员。""",

    "第8章-文件操作": """文件操作使用 stdio.h 中的 FILE 类型和相关函数。
fopen(path,mode) 打开文件，mode 常用 "r" 读、"w" 写（清空）、"a" 追加，加 b 表示二进制。
fopen 失败返回 NULL，打开后必须判空：FILE *fp=fopen("a.txt","r"); if(fp==NULL)...
fclose 关闭文件并刷新缓冲区，文件用完必须关闭，否则可能数据丢失。
fscanf/fprintf 按格式读写文件，用法与 scanf/printf 类似，第一个参数是 FILE*。
fgets 每次读一行（含换行符），常用于逐行处理文本文件。
fread/fwrite 二进制块读写：fread(buf,size,count,fp)。
feof 判断是否到达文件尾，注意它是在读取失败后才返回真。
文件指针移动：fseek(fp,offset,SEEK_SET); ftell 返回当前位置；rewind 回到开头。
检查文件是否存在：fopen 成功即存在（"r" 模式），失败不代表一定不存在需看 errno。""",
}

doc = fitz.open()
for name, content in chapters.items():
    lines = [ln for ln in content.strip().split("\n")]
    page = doc.new_page()
    page.insert_text((72, 50), name.replace("-", " "), fontsize=15, fontname="china-s")
    y = 85
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=10.5, fontname="china-s")
        y += 19
doc.save("/tmp/C程序设计-第1-8章-完整版.pdf")
print(f"生成完成：{len(doc)} 页")
PYEOF

echo "=== 2. 上传解析 ==="
KB=$(curl -s --max-time 10 $BASE/api/kb | .venv/bin/python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
DOC=$(curl -s --max-time 30 -X POST $BASE/api/kb/$KB/documents -F "file=@/tmp/C程序设计-第1-8章-完整版.pdf" \
  | .venv/bin/python -c "import sys,json;print(json.load(sys.stdin)['doc_id'])")

set +e
for i in $(seq 1 30); do
  STATUS=$(curl -s --max-time 10 $BASE/api/kb/$KB/documents/$DOC)
  echo "[$i] $STATUS"
  echo "$STATUS" | grep -qE '"status":"(parsed|failed)"' && break
  sleep 3
done
set -e
echo "KB_ID=$KB" > /tmp/e2e_kbid.txt
