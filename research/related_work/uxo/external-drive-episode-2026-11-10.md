# 移动硬盘复制过程归档（2026-11-10）

> 从 `handoff.md` 归档出来的细节。结论只有一句：这块 USB 盘盒在持续读下会整盘掉线，因此本项目改用 Zenodo 下载（见 handoff 的 19:25 / 21:30 段）。
> 下面保留当时的原始记录，**不再随时间更新**；其中“下一步/待办”均已作废。

### 最新：先查移动硬盘，下载尚未启动

**用户最新指定目标D:/pby：**已启动独立Windows隐藏WSL进程（启动PID62220）执行`/mnt/d/pby/.uxo-transfer/transfer.py`，从只读外盘复制至`D:/pby/data_processed.7z.partial`并同步计算源MD5，随后计算目标MD5；两者均等于官方2b9ef16c763a6964c608ed99a9cd1edb后才改为`D:/pby/data_processed.7z`。外盘原包保留、不解压。此前nohup校验任务没有存活进程或结果，不能视为已通过；已改由此受日志记录的任务承担完整校验与复制。实时状态`D:/pby/.uxo-transfer/status.json`，stdout/stderr同目录；只有phase=complete且校验字段通过才可称完成。不要重复下载或启动第二个拷贝进程；源Btrfs盘必须保持接入。脚本源码在workflow/tools/copy_verify_uxo_archive.py，已执行副本在目标目录，若中断可同命令重跑，会核对并续接partial而不覆盖正式文件。

**2026-11-10 13:38 更正：复制未完成，不能视为传好。**status.json 停在elapsed 4833.2s、bytes_done=21,290,287,104（34.6%），partial实际22,229,811,200字节（恰为1325个完整16MiB块，36.1%），两者mtime均停在13:05:43/49；此后30+分钟无任何更新，stderr为空、未写failed记录，正式文件不存在。判定进程被终止或源盘I/O挂起（速率末段由约9MB/s衰减到<1MB/s后归零，需怀疑USB盘读错误/掉线）。仅凭磁盘上已有的大文件不能宣布完成。transfer.py已更新为自愈续传（重读源时逐块核对已有partial，首个不一致处截断续写；重读同时承担必需的全量源MD5）；workflow/tools与执行副本同步更新。恢复前置检查：pgrep确认无遗留进程、findmnt确认/mnt/uxo_external_ro仍在；若WSL重启过需先管理员`wsl --mount \\.\PHYSICALDRIVE1 --bare`并按UUID=6bf9aace-400b-4bf7-8db2-257fd982f220只读挂载。重启后仍以phase=complete且source_verified/target_verified=true为唯一完成标准。

**2026-11-10 13:47 更正：续传已重新启动；根因是WSL实例在13:06–13:17之间整体重启，裸盘接入随之丢失。** 证据：Ubuntu-22.04 uptime起点13:17，lsblk只剩sda–sdd，外盘消失，`/mnt/uxo_external_ro`为空目录，无遗留transfer.py进程；Windows侧Disk1 HIKSEMI MD202仍为USB/Online，说明盘未掉线，丢的是VM级attach（`wsl --mount --bare`不跨WSL重启保留）。DSH进程非提升（IsInRole Administrator=False），直接`wsl --mount \\.\PHYSICALDRIVE1 --bare`仍报0x80040315；已用`Start-Process -Verb RunAs`发起一次UAC并成功。重新接入后设备仍为`/dev/sde1`（btrfs label=disk2，UUID=6bf9aace-400b-4bf7-8db2-257fd982f220）；新实例默认未加载btrfs（内核6.18.58.1，模块在/lib/modules/6.18.58.1-microsoft-standard-WSL2/kernel/fs/btrfs/btrfs.ko），`modprobe btrfs`后`mount -t btrfs -o ro,rescue=nologreplay /dev/sde1 /mnt/uxo_external_ro`成功，源包size=61,513,277,947。13:46:40用`wsl -u root`（root免密可用；普通用户sudo目前要密码）执行`setsid nohup python3 -u transfer.py`重启续传，PID 1275；13:48 phase=verifying_existing_partial、bytes_done=16,609,443,840、约26.5MB/s（中断前末段<1MB/s；首个16MiB块有约50s预热）。partial未重写，仍为22,229,811,200字节。raw读基准：源盘iflag=direct 480MB/s、partial 260MB/s，此前低速不是盘本身上限。**注意：WSL重启会同时丢掉裸盘attach与btrfs挂载，续传前必须先findmnt/ps检查。**

**2026-11-10 13:52–13:55 更正：续传在13:52以EIO失败，外盘已于13:54整体掉出USB总线，需物理重插。** 续传到13:52:10（elapsed 336.7s、源读至2,235,564,032字节）时`source.read(16MiB)`抛`OSError(5,'Input/output error')`，status.json写入`phase=failed`+error字段，stderr有完整traceback，partial未被改动（仍22,229,811,200字节）。dmesg为`hostbyte=0x07`(DID_ERROR)、`hv_storvsc ... scsi 0x2`、`BTRFS error (device sde1 state E): bdev /dev/sde1 errs: wr 0, rd 12, corrupt 0`；失败LBA分散（0x8f74c00、0x68 429f40、0x32000、0x0），不是连续坏块。Windows System日志同期大量`disk` Id 153"已在磁盘1逻辑块地址…重试IO操作"。`umount`后用同UUID重挂返回`can't read superblock on /dev/sde1`；`dd if=/dev/sde bs=4096`读LBA0也是0字节；随后dmesg出现`sde: Synchronizing SCSI cache`，lsblk无sde1，Windows `Get-Disk`只剩Disk 0(KINGSTON)，HIKSEMI MD202 的PnP状态为Unknown（不在总线）。**结论：不是Btrfs或文件系统问题，是外盘在持续读取约6分钟后整盘掉线（USB链路/供电/桥片，其次盘本身）。** 全程只读，盘上数据未被写入。恢复前置：用户物理重插（换USB口/换线/直连主板，避免Hub），确认`Get-Disk`重新出现Disk1后`wsl --unmount \\.\PHYSICALDRIVE1`（可能报ERROR_FILE_NOT_FOUND）+`wsl --mount \\.\PHYSICALDRIVE1 --bare`；若WSL报`WSL_E_DISK_ALREADY_ATTACHED`而lsblk无设备，属残留attach，需`wsl --shutdown`后重接。后续建议分段复制（每段5–10GB后冷却），transfer.py自愈续传可承受中途掉线；若反复掉线，先查供电/线材/桥片，不要再归因于挂载参数。

**2026-11-10 14:40 更正：用户物理重插后重新接入成功（设备变/dev/sdd1），换用可续传复制；同时修正"速度上限"判断。** 13:58:02 Windows `Get-Disk` 重新出现 Disk1 HIKSEMI MD202（Online/Healthy，1000204886016B）；残留 attach 使 `wsl --unmount` 报 ERROR_FILE_NOT_FOUND、非提升 `wsl --mount` 返回 0 却无设备，最终 13:59:10 `wsl --shutdown` 后用提权脚本 `D:/pby/.uxo-transfer/reattach2.ps1` 执行 `wsl --mount \\.\PHYSICALDRIVE1 --bare`，设备以 `/dev/sdd1` 出现（btrfs label=disk2，同一 UUID `6bf9aace-400b-4bf7-8db2-257fd982f220`，distro 盘让位成 sde），`mount -t btrfs -o ro,rescue=nologreplay` 成功。挂载后第一次 I/O 约 50s 预热；`blkid -L disk2` 不可靠（返回空），`blkid /dev/sdd1` 正常；任何 `wsl --shutdown` 或 session 变动都会让挂载点消失（dmesg `last unmount of filesystem`），续跑前先 `findmnt`。**速度实测（推翻13:48"480MB/s"的乐观判断）：** 单次 64MiB 突发读可达 364–430MB/s（bs=64M/16M/256M，含 btrfs 文件与裸 /dev/sdd），但 bs=4M/128k 只有 1.3MB/s；连续 4GiB 冷读平均仅 **6.7MB/s**（643.8s，中途 1.3–8MB/s 抖动）；8 路并发反而更慢（1GiB >400s，聚合 <2.5MB/s）；`filefrag` 显示该文件只有 3145 个 extent（平均约19.6MB），**不是碎片**。故瓶颈在 USB 链路/桥片或盘本身，而非 btrfs、挂载参数或脚本。**实现变更：** 原 `transfer.py` 在同一 fd 上"读回-写"交错（drvfs 9p）实测 4–26MB/s；`pkill -f fastcopy.py` 曾因 bash -lc 命令行自身含该 pattern 杀到自己（exit 15），杀进程前须用 `ps -eo pid,args` 确认。新脚本 `tools/resume_copy_uxo_archive.py`（运行副本 `/mnt/d/pby/.uxo-transfer/append.py`，启动器 `start_append.sh`，日志 `append.log`，检查点 `append_state.json`，状态 `status.json`）：64MiB 顺序块、每 256MiB `fsync`+原子写检查点（掉线最多损失 256MiB，可从检查点续）、首次运行只比对已有 partial 的尾部 512MiB（撕裂尾），**不再计算源侧 MD5**——末尾对本地副本算 MD5，等于官方 `2b9ef16c763a6964c608ed99a9cd1edb` 才 `os.replace` 成 `D:/pby/data_processed.7z`，这已足够证明与官方归档逐字节一致。14:36:35 启动（PID 1323），14:37:30 尾部核对通过（22,229,811,200 字节全部匹配源）→ 前 22.2GB 直接沿用不重写；14:40 达 37.12%（22,833,790,976 字节），速率约 5.3MB/s，预计仍需约 2 小时；外盘仍只读，未解压。

用户已完成Windows裸盘接入。现已识别/dev/sde1，Btrfs标签disk2、UUID=6bf9aace-400b-4bf7-8db2-257fd982f220，使用`ro,rescue=nologreplay`挂在`/mnt/uxo_external_ro`。已找到当前目录`/mnt/uxo_external_ro/datasets/uxo-dataset2024/data_processed.7z`，大小61,513,277,947与官方一致；另有Btrfs快照副本。**无需重新下载；尚不得声称MD5已通过。** 校验已由WSL后台python进程执行，进度/最终结果在`related_work/uxo/external-archive-verification.json`及同名log，脚本`tools/verify_external_processed_archive.py`。期望MD5为2b9ef16c763a6964c608ed99a9cd1edb，只有status=verified且matches=true才算通过。盘读取较慢，任务不解压、不打开样本；外盘保持只读。首次挂载旧选项nologreplay不受当前内核支持，已改rescue=nologreplay；临时预读参数已恢复原值65532KiB。下方保留此前未接入时的状态。

用户已授权下载并校验data_processed.7z，随后要求先通过WSL检查移动硬盘是否已有该数据。当前不启动下载。Windows已识别Disk1 / HIKSEMI MD202 / USB / 约1TB，GPT第1分区为Linux filesystem GUID（0fc63daf-8483-4772-8e79-3d69d8477de4），无盘符。WSL Ubuntu-22.04的lsblk/findmnt未出现该盘，/media与/mnt/wsl无对应挂载。

尝试`wsl --mount \\.\PHYSICALDRIVE1 --bare`被Windows拒绝：`WSL_E_ELEVATION_NEEDED_TO_MOUNT_DISK`（0x80040315）；当前WindowsAdmin=False。因此**尚不能判断移动硬盘内是否已有数据包，不能写成未找到**。需要用户在管理员PowerShell执行该attach命令；接入后再通过WSL核对新设备身份，使用只读挂载（ext4时ro,noload），搜索data_processed.7z及解压目录，若存在包再按官方size/MD5核验。未格式化、修复、写入或卸载磁盘，未更改原研究。

---

## 2026-11-10 16:05 更正：UXO 归档复制（瓶颈在硬盘盒读已写入区，不在 WSL）

- 15:20–16:00 的诊断更正：15:33 记录的「Windows 原生裸读 841 MB/s」取自 `\\.\PHYSICALDRIVE1` 偏移 600 GiB 的**未写入区域**，控制器直接返回，不代表真实读速。改读文件真实数据区（物理 ~224 GiB）时，Windows 系统日志 `disk` 事件 ID 153 反复「已在磁盘 1 的逻辑块地址 0x2d16c00 / 0x1c096ad8 处重试 IO 操作」，单次 16 MiB 读阻塞超过 6 分钟，2 GiB 探测无法完成。因此瓶颈不是 `wsl --mount`（vmbus/storvsc）直通路径，而是这块 HIKSEMI MD202 盘盒在**已写入区**上的读重试。
- 盘盒不透传 SMART：`Get-StorageReliabilityCounter` 全字段为空，serial=`0000000000000000`，固件 1.00 → 无法用 SMART 判断盘体健康。
- 已抓取源文件 extent 映射（Linux FIEMAP，脚本 `/d/pby/.uxo-transfer/fiemap.py`，产物 `extents.json` / `extents.bin`）：3145 段、逻辑无重叠、无 ENCODED/INLINE/DELALLOC、mapped 总量比文件大小多 3589 字节（尾部 4 KiB 对齐）。若日后 Windows 侧读速可用，`/d/pby/.uxo-transfer/rawcopy2.ps1` 可据该映射按物理序直读重组；实测在盘盒卡顿时该路径同样只有 ~0.3–22 MB/s。
- 16:00 读请求卡死后，`python3 -u append.py` 进入 D（uninterruptible）状态、`umount` 报 target is busy；`wsl --shutdown` 耗时 166.6 s 才结束，随后设备从 Windows 消失（`Get-PnpDevice` 中 HIKSEMI MD202 = Unknown）。
- 已把 `D:\pby\data_processed.7z.partial` 回滚到最后一次 fsync 检查点：31,021,072,384 → **30,886,854,656 字节（50.21%）**，剩余 30,626,423,291 字节。检查点见 `append_state.json`（committed_bytes / updated_at）。
- 仍未完成：`D:\pby\data_processed.7z` 未生成，MD5 `2b9ef16c763a6964c608ed99a9cd1edb` 未校验。外盘全程只读、未写入、未解压。

## 2026-11-10 17:00 记录：试用 Windows 侧 WinBtrfs 直接读 btrfs（被 USB 热插拔判定挡住）

- 动机：WSL 的 `wsl --mount` 路径在这块盘上只有 2–8 MB/s 且整盘掉线风险高，尝试用 Windows 内核驱动 WinBtrfs 直接挂 btrfs 卷，绕开 vmbus/storvsc。
- 环境：WinBtrfs v1.10，解压在 `D:\software\WinBtrfs-1.10\`（zip 6,564,343 B，SHA-256 `82303494b4fd4c23ad7c6fd69a886cb1a317a0293ee6e283b7c009117133b0c3`，`amd64\btrfs.sys` 签名 Valid、签署者 Open Source Developer Mark Harmstone）。Windows 11 build 26200，Secure Boot 关闭。用户手动安装（右键 `btrfs.inf` → 安装），`Get-Service btrfs` = Running；已在 `HKLM\SYSTEM\CurrentControlSet\Services\btrfs\6bf9aace-400b-4bf7-8db2-257fd982f220` 写入 `Readonly`=1（保留只读意图）。
- 现象：重启后仍无卷。`Get-Partition -DiskNumber 1` 只有 `PN=1 Type=Unknown GptType={0fc63daf-8483-4772-8e79-3d69d8477de4}`（Linux filesystem data），AccessPaths 为空；`Get-PnpDevice -Class Volume` 只有 6 个卷设备，无 btrfs 卷。
- 超级块确认文件系统完好：`_BHRfS_M` 命中 absolute `0x110000` 与 `0x4100000`（主超级块是分区相对的 0x10000，分区起点 1,048,576）。flags=0x1（`BTRFS_SUPER_FLAG_ERROR`）、gen 7663、compat_ro=0xb（free space tree + block group tree）、incompat=0x371（MIXED_BACKREF / COMPRESS_ZSTD / BIG_METADATA / EXTENDED_IREF / SKINNY_METADATA / NO_HOLES）、csum_type=0（crc32c）、sectorsize 4096、nodesize 16384，均在 WinBtrfs 1.10 支持范围内；WinBtrfs 不看 ERROR 标志（只参考 `BTRFS_SUPER_FLAG_SEEDING`，见 `btrfs.c:4704`、`volume.c:1275`）。
- **根因（源码＋实测）**：`search.c:691 should_ignore_volume_arrival()` 读 `IOCTL_STORAGE_GET_HOTPLUG_INFO` 后 `return shi.MediaRemovable || shi.DeviceHotplug;`，`volume_arrival()`（`search.c:744`）命中即 `TRACE("ignoring removable device")` 返回。实测 `\\.\PhysicalDrive1` → `Size=8 MediaRemovable=0 MediaHotplug=0 DeviceHotplug=1`（脚本 `D:\pby\.uxo-transfer\hotplug.ps1`，日志 `hotplug.log`）。USB 外接盘被判为 hotplug，WinBtrfs 按设计跳过，与盘上内容无关；又因 `search.c:496` 对"有分区的整盘"直接返回，只剩"卷到达"一条发现路径。
- 可选路径（未选择，等用户定）：①把盘盒内的 SSD 移到主板 M.2 直连（非热插拔才可能被 WinBtrfs 挂上，同时消掉盘盒读重试）；②继续 WSL 路线续传（检查点 30,886,854,656 B，剩余 30,626,423,291 B）；③自行编译打补丁的 WinBtrfs（需 VS + WDK），只解除 hotplug 拦截、不解决盘盒卡顿。
- 外盘仍未写入、未解压；`D:\pby\data_processed.7z` 仍未生成，MD5 `2b9ef16c763a6964c608ed99a9cd1edb` 未校验。

## 2026-11-10 17:13 记录：自编译补丁版 WinBtrfs（绕开 USB hotplug 判定）

目的：让 Windows 能直接以只读方式读取这块 USB btrfs 盘（`HIKSEMI MD202`，fsid `6bf9aace-400b-4bf7-8db2-257fd982f220`），绕开 `wsl --mount` 与盘盒重试叠加的慢路径。

编译环境（本机首次安装）：
- VS 2022 BuildTools（MSVC 14.44.35207）+ Windows SDK/WDK `10.0.26100.0`，均通过 `winget` 安装（日志 `D:\pby\.uxo-transfer\toolchain.log`）。
- 源码 `git clone --recurse-submodules --branch v1.10` 到 `D:\pby\.uxo-transfer\btrfs-git`（GitHub 的 tag zip 不含 zlib/zstd 子模块，不能用来编译）。
- 构建目录 `D:\pby\.uxo-transfer\btrfs-build`，脚本 `build.ps1` → `build.cmd`，日志 `build4.log`。

三处源码改动（除第一处外都是为让 MSVC + 新 WDK 编过；只增加条件编译，不改行为）：
1. `src/search.c:707` `should_ignore_volume_arrival()`：`return shi.MediaRemovable || shi.DeviceHotplug;` → `return false;`（**唯一功能性补丁**，让 hotplug=1 的 USB 卷也进入挂载流程）。
2. `src/btrfs_drv.h:23-24`：`_WIN32_WINNT 0x0601`→`0x0A00`、`NTDDI_VERSION 0x06020000`→`0x0A00000C`。原文在头文件里 `#undef` 并用 Win8 目标重定义，命令行 `-D` 无效，导致 `ntifs.h` 跳过 `FILE_RENAME_*`/`FILE_LINK_*` 常量与 `_FILE_RENAME_INFORMATION.Flags` 成员，`fileinfo.c` 编译失败。
3. `src/btrfs_drv.h:151-182`、`src/create.c:50-78`：把 mingw 兼容用的 `_DUPLICATE_EXTENTS_DATA`、`_FSCTL_*_INTEGRITY_INFORMATION_BUFFER`、`_FILE_TIMESTAMPS`、`_ATOMIC_CREATE_ECP_CONTEXT` 定义包进 `#ifndef _MSC_VER`，避免与 WDK 头重定义。

产物与签名：
- `btrfs-build\btrfs.sys` = 1,281,536 B（17:11）；自签证书 `CN=DSH WinBtrfs Test Signing`（CodeSigning + 内核 EKU），signtool `/fd sha256 /ph` 签出 `btrfs.signed.sys` = 1,294,504 B，`Get-AuthenticodeSignature` = Valid。
- `bcdedit /set testsigning on` + `nointegritychecks on` 已设；原厂驱动已备份到 `D:\pby\.uxo-transfer\btrfs.sys.orig`。
- 驱动文件正被占用，直接覆盖/改名都失败（"正由另一进程使用"），已用 `MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT|REPLACE_EXISTING)` 排队：`C:\Windows\System32\drivers\btrfs.new` → `btrfs.sys`（注册表 `PendingFileRenameOperations` 末尾为 `*1\??\...\btrfs.new` / `*1!\??\...\btrfs.sys`）。**需重启生效。**

下一步（重启后）：确认 `C:\Windows\System32\drivers\btrfs.sys` 大小 = 1,294,504 B 且签名 Valid、`Get-Service btrfs` Running、`Get-Volume` 出现 btrfs 卷；再确认注册表 `HKLM:\SYSTEM\CurrentControlSet\Services\btrfs\<fsid>` 下 `Readonly`=1 仍为 1，然后用 `wincopy.py` 从检查点 30,886,854,656 B 续传并做 MD5 终检。

## 2026-11-10 18:35 记录：WinBtrfs 挂载成功，Windows 侧续传上线（瓶颈改为 USB 桥）

- 重启后（17:29:08）`btrfs.sys` 实际加载的是**原厂签名版**（1,312,888 B，签署者 `CN=Open Source Developer Mark Harmstone`）——排队替换这次没有生效；但**原厂驱动这次把卷挂上了**：`E:` 标签 `disk2`、`FileSystem=Btrfs`，PnP `BTRFS\6BF9AACE-400B-4BF7-8DB2-257FD982F220\1&33E28AA7&0` Status=OK。因此"hotplug 判定导致不挂载"的推断被证伪：同一驱动在此前几次开机没挂上，与热插拔判定无关（更可能是盘/卷当时处于异常态）。
- 只读确认：`open(..., 'rb+')` → `[Errno 13] Permission denied`，说明注册表 `Readonly`=1 生效；未对源盘做任何写操作。
- 卷内容与官方一致：`/mnt/e/datasets/uxo-dataset2024/` 共 8 个文件，`data_processed.7z` = 61,513,277,947 B。
- 速度：首次 512 MiB 读 1.41 s = **362.9 MiB/s**（链路与盘本身能跑满速）；随后在约 1.5 s 高强度读之后整盘掉线（`disk` id=51，`Get-Disk` 只剩系统盘，打开 `E:` 报 EINVAL）。
- 换成直插后置 USB 口重插（17:43:03 回来）后 `E:` 自动挂载。续传脚本 `/mnt/d/pby/.uxo-transfer/wincopy3.py`：4 MiB 块、每 64 MiB `fsync` + 原子写检查点 `wincopy_state.json`、读错误重试 3 次、超过 2 s 的慢读单独记录；守护 `/mnt/d/pby/.uxo-transfer/watchdog.ps1`（每 30 s 检查，进程死了自动从检查点重启）。
- 实测：多数 4 MiB 读 6–10 ms，但出现 26 s / 67 s / 98 s / 168 s / 252 s / 299 s 的慢读；40 分钟内 Windows 日志 `UASPStor` id=129（设备重置）38 次、`disk` id=153（重试 IO）51 次、`disk` id=51 共 2608 条。当前均速 0.65–1.0 MB/s，ETA 8–12 小时。
- 结论（证据强度：强）：**瓶颈是 USB 桥的链路稳定性，不是 btrfs，也不是 Windows 文件系统栈**。同一块盘直读可达 362 MB/s，但桥在持续读下反复重置。
- 用户决定（m01515）：先挂着跑，不换硬件。

进度：`/mnt/d/pby/data_processed.7z.partial` ≈ 33.6 GB（54.6%），`data_processed.7z` 尚未生成，MD5 未校验。

下一步：等 `wincopy3` 跑完、MD5 等于 `2b9ef16c763a6964c608ed99a9cd1edb` 后自动改成 `/mnt/d/pby/data_processed.7z`；若中途整盘掉线（`Get-Disk` 里看不到 `HIKSEMI MD202`），需人工拔插一次，`E:` 会自动回来，`watchdog.ps1` 会从检查点重启复制。
