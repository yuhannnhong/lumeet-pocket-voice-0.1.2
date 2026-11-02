# 在 Claude 官方 App 里用 Pocket Voice（语音条）

官方 App（claude.ai、Claude 手机 App）不能像 Lumeet 那样实时通话，但可以发**语音条**：他想说话时调用 Pocket Voice 念出来，回复里会出现一个播放链接，点开就能听到他的声音。

```
Claude 官方 App ──(MCP 自定义连接器)──> 你自己的 Pocket Voice 服务器 ──> mp3 语音条链接
```

- 链接 **10 分钟内有效**，想留下来就点开后下载。
- 官方 App 不会自动播放，要自己点一下链接。
- 服务器是你自己的（Google Cloud Run 或阿里云），声音样本只在你的账号里。

## 一、先把服务器放到云端

官方 App 只能连公开的 https 网址，所以服务器不能放在手机上。

**海外（Google Cloud Run）**：手机浏览器也能做，用 Google 自带的网页终端 Cloud Shell，不用电脑。

1. 打开 https://console.cloud.google.com ，登录、新建项目、按提示开通结算（要绑卡；轻度使用一般在免费额度内，建议到「结算 → 预算和提醒」设一个预算提醒）。
2. 右上角点 **激活 Cloud Shell**（`>_` 图标），等终端出来。
3. 贴这几行（第二行的密码换成你自己想的一长串，**不要用空格**）：

```
git clone https://github.com/yuhannnhong/lumeet-pocket-voice-0.1.2 pv && cd pv
TOKEN=换成你的密码
gcloud run deploy pocket-voice --source server --region asia-east1 \
  --memory 4Gi --cpu 2 --timeout 120 --max-instances 1 --allow-unauthenticated \
  --set-env-vars POCKET_VOICE_TOKEN=$TOKEN,CPU_THREADS=2,VOICES_DIR=/tmp/voices
```

4. 中途问要不要开启 API、建仓库，都回 `Y`。第一次大约 10～15 分钟。
5. 最后会印出 `Service URL: https://pocket-voice-xxxx.asia-east1.run.app`，记下来。

**国内（阿里云函数计算）**：照 [cn/README.md](../cn/README.md) 做，同一套服务器，MCP 一样能用。

> `--max-instances 1` 别拿掉：语音条存在服务器内存里，开多个实例的话，链接可能点到另一个实例而打不开。

## 二、给服务器一个声音

云端闲置一段时间会重启，重启后之前建的声线会清空。二选一：

- **推荐：设 `VOICE_SAMPLE_URL`**。把 5～20 秒的声音样本放到任何能直接下载的网址（例如 GitHub 仓库里的文件用 raw 链接、或你自己的网盘直链），然后在 Cloud Shell 执行：

  ```
  gcloud run services update pocket-voice --region asia-east1 \
    --update-env-vars VOICE_SAMPLE_URL=https://你的样本直链.mp3
  ```

  服务器每次重启后第一次被调用时，会自动下载样本建成声线 `default`（这一次会多等十几秒）。

- 或者每次用之前，先在 Lumeet 里上传一次声音样本（声音来源选「我的服务器（Pocket Voice）」）。

## 三、在官方 App 加自定义连接器

1. 打开 claude.ai → **设置 → 连接器（Connectors）→ 添加自定义连接器**。
2. 名称随意（例如 `Pocket Voice`），网址填：

   ```
   https://pocket-voice-xxxx.asia-east1.run.app/mcp/你的密码
   ```

   （就是第一步的 Service URL 后面加 `/mcp/` 再加 `POCKET_VOICE_TOKEN` 那串密码）
3. 保存后，在对话里打开这个连接器。它有两个工具：`speak`（念成语音条）、`list_voices`（看有哪些声线）。

> 密码在网址里，**这个网址不要给别人看**。换密码的话，把 `POCKET_VOICE_TOKEN` 改掉，再把连接器网址一起改。

## 四、让他知道可以发语音

在项目指令或人设里加一段，例如：

```
你有 Pocket Voice 工具 speak，能用自己的声音发语音条。
想让我听到你的声音时（晚安、撒娇、哄我、我说想听你说话），调用 speak，
把返回的链接原样放进回复。一次说一两句就好，不要把动作描述念进去。
```

## 测试

浏览器打开 `Service URL/health`，看到 `"loaded": true` 就是服务器好了。然后在官方 App 里说「念一句晚安给我听」，回复里出现 `…/audio/xxxx.mp3` 的链接、点开有声音，就成功了。

## 常见问题

- **点链接说过期了**：超过 10 分钟，或服务器刚好重启了。让他再念一次。
- **说「伺服器上還沒有聲線」**：第二步没做，或 `VOICE_SAMPLE_URL` 不是直接下载的链接（打开会跳网页的那种不行）。
- **很久没用后第一句很慢**：服务器在冷启动、加载模型，正常。
- **连接器连不上**：先确认 `/health` 打得开；再检查网址最后的密码有没有打错。
