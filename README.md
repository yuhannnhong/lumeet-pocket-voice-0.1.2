# Pocket Voice

给 AI 伴侣的轻量本地 TTS：导入一次声音样本，之后在手机或电脑上，都用同一个声音说话。

- 上传一段 5～20 秒的声音样本，之后任何中文都用这个声音念
- 安卓手机本地跑，不联网也能说话，不按次收费
- iPhone 也能用：连自己的电脑（Mac、Windows 都行）
- 接口跟 OpenAI 一样（`/v1/audio/speech`），Operit、Lumeet 这类 App 直接填就能用
- 模型和声音只放在你自己的手机或电脑里，我们不帮任何人托管

## 下载

**安卓 APK（0.1.2）**：到右边的 [Releases](../../releases/latest) 下载 `pocket-voice-0.1.2.apk`。

第一次打开 App 点「下载模型」（约 560 MB），断了再点一次会接着下。

## 用法

| 你有什么 | 看哪里 |
|---|---|
| 安卓手机 | 装 APK，或 [Termux 版](android/termux/README.md)、[Operit 版](android/operit/README.md) |
| iPhone、自己的电脑（Mac、Windows、mini PC） | [server/](server/README.md)，见下面「iPhone 连电脑」 |
| 大陆 iPhone、没有电脑 | [cn/](cn/README.md)，放到自己的阿里云函数计算（国内镜像，不用翻墙） |
| Hugging Face 付费硬件 | [hf-space/](hf-space/README.md)（免费 CPU 已经不能用） |

### 安卓 App 快速上手

1. 装好 APK，打开后点「下载模型」。
2. 点「＋ 新增声线」，选一段 5～20 秒、干净、没有背景音乐的录音。
3. 输入一句话试听。
4. 点「开启服务器」，通知栏会一直有个小图标，屏幕关了也能说话。
5. **先在 App 的「设置」填一个密码**（Lumeet 一定要有密码才会启用）。
6. Operit：语音 → TTS 引擎选「HTTP API（远程）」，照 App 里「给 Operit 的填法」抄（网址、方法、请求内容，API Key 填密码）。
7. Lumeet：设置 → API 统一管理 → 角色 → 声音来源选「我的服务器（Pocket Voice）」，网址填 `http://127.0.0.1:7860`、填密码，再上传一次声音样本。
8. 小米、HyperOS：电池设置改「无限制」、开「自动启动」，不然会被系统杀掉。

### iPhone 连电脑

1. 电脑装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并打开。
2. 下载本仓库（Code → Download ZIP），在 `server` 文件夹打开终端机，执行（密码自己换）：
   ```
   docker build -t pocket-voice .
   docker run -d --restart unless-stopped -p 7860:7860 -e POCKET_VOICE_TOKEN=你的密码 -e VOICES_DIR=/data -v pocket-voice:/data --name pocket-voice pocket-voice
   ```
   第一次会下载模型（约 730 MB）。电脑浏览器打开 `http://127.0.0.1:7860/health`，看到 `"loaded": true` 就好。
3. 电脑和 iPhone 都装 [Tailscale](https://tailscale.com/)，登同一个账号。
4. 电脑终端机再执行 `tailscale serve --bg 7860`，它会给一个 `https://电脑名.xxx.ts.net` 的网址（iPhone 上的网页 App 只能连 https，所以要这一步）。
5. Lumeet：设置 → API 统一管理 → 角色 → 声音来源选「我的服务器（Pocket Voice）」，填这个 https 网址和密码，再上传声音样本。

电脑要开着、不能睡眠，手机才有声音。

## 速度参考（实测）

| 跑在哪里 | 一句话 |
|---|---|
| 中高端安卓手机（APK 本地） | 约 2～3 秒 |
| 入门安卓手机（例如 Redmi 14C） | 约 30 多秒，比较适合发语音条 |
| 云主机 CPU | 短句 1 秒多，长句最慢约 7 秒 |

手机慢的话，改用自己的电脑或云主机会快很多。

## 模型与授权

- 模型：[OpenMOSS / MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano)（约 1 亿参数，Apache-2.0）
- 本项目：Apache-2.0，见 [LICENSE](LICENSE)、[NOTICE](NOTICE)

请只用你有权使用的声音，不要拿别人的声音冒充本人。
