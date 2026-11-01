# Pocket Voice

给 AI 伴侣的轻量本地 TTS：导入一次声音样本，之后在手机、电脑或云端，都用同一个声音说话。

- 上传一段 5～20 秒的声音样本，之后任何中文都用这个声音念
- 安卓手机本地跑，不联网也能说话，不按次收费
- iPhone 也能用：连自己的电脑，或复制到自己的 Hugging Face（免费 CPU）
- 接口跟 OpenAI 一样（`/v1/audio/speech`），Operit、Lumeet 这类 App 直接填就能用
- 模型和声音只放在你自己的手机、电脑或云端账号里，我们不帮任何人托管

## 下载

**安卓 APK（0.1.2）**：到右边的 [Releases](../../releases/latest) 下载 `pocket-voice-0.1.2.apk`。

第一次打开 App 点「下载模型」（约 560 MB），断了再点一次会接着下。

## 用法

| 你有什么 | 看哪里 |
|---|---|
| 安卓手机 | 装 APK，或 [Termux 版](android/termux/README.md)、[Operit 版](android/operit/README.md) |
| 自己的电脑（Mac、mini PC） | [server/](server/README.md) |
| iPhone、没有电脑 | [hf-space/](hf-space/README.md)，复制到自己的 Hugging Face |

### 安卓 App 快速上手

1. 装好 APK，打开后点「下载模型」。
2. 点「＋ 新增声线」，选一段 5～20 秒、干净、没有背景音乐的录音。
3. 输入一句话试听。
4. 点「开启服务器」，通知栏会一直有个小图标，屏幕关了也能说话。
5. 在 Operit / Lumeet 里填 `http://127.0.0.1:7860`（App 里有「给 Operit 的填法」可以照抄）。
6. 小米、HyperOS：电池设置改「无限制」、开「自动启动」，不然会被系统杀掉。

## 模型与授权

- 模型：[OpenMOSS / MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano)（约 1 亿参数，Apache-2.0）
- 本项目：Apache-2.0，见 [LICENSE](LICENSE)、[NOTICE](NOTICE)

请只用你有权使用的声音，不要拿别人的声音冒充本人。
