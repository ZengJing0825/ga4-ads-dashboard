# GA4 + Google Ads 看板

自托管的小型增长看板。每天通过 **GA4 Data API** 和 **Google Ads API** 拉取数据，
校验后渲染成一个静态 **Chart.js** 页面(漏斗、渠道拆分、流量来源、地域、广告花费、
广告系列表格)。定时任务用 **macOS launchd**，不需要数据库和后端框架。

> **仓库自带的数据是合成的。** `dashboard/data.sample.json` 是随机生成的演示数据
> (`"synthetic": true`)，只为让看板开箱即可渲染，不代表任何真实的资产、账户或产品。

## 流程

```
launchd (本地时间 09:00 / 14:00)
  └─ refresh.sh
       ├─ 锁文件 + 300s 超时看门狗 + 日志轮转
       ├─ 备份 dashboard/data.json(保留最近 7 份)
       ├─ [1/4] scripts/fetch_ga4.py         GA4 Data API  -> data/ga4_data.json
       ├─ [2/4] scripts/fetch_google_ads.py  Google Ads API -> data/google_ads_data.json
       ├─ [3/4] 合并                          -> dashboard/data.json
       └─ [4/4] scripts/validate_data.py     失败 -> 恢复备份 + macOS 通知
```

`dashboard/index.html` 是静态页面，读取同目录下的 `data.json`；不存在时回退到
`data.sample.json`。

事件名都是通用示例。改 `scripts/fetch_ga4.py` 顶部的事件列表和
`dashboard/index.html` 里的 `NAME_MAP` / 漏斗数组即可换成你自己的 GA4 事件。

## 快速预览(仅演示数据)

```bash
python3 -m http.server 8787 -d dashboard
# 打开 http://localhost:8787
```

页面用 `fetch()` 读 JSON，必须通过 HTTP 访问，不能直接 `file://` 打开。

## 接真实数据

1. `pip install -r requirements.txt`
2. GA4:创建 service account,下载 JSON key 到 `credentials/`,启用 Google Analytics
   Data API,并在 GA4 -> 管理 -> 属性访问权限管理中把该 service account 加为 Viewer。
3. Google Ads:申请 developer token,在 Google Cloud Console 创建 Desktop app 类型的
   OAuth client,把 client id / secret 填进 `.env`,运行
   `python3 scripts/get_refresh_token.py` 拿到 refresh token。
4. `cp .env.example .env` 并填好占位符。`REPORT_TZ_OFFSET_HOURS` 设成 GA4 资产 /
   Ads 账户的时区偏移。
5. `./refresh.sh` 跑一次;`./install.sh` 安装 launchd 定时任务
   (会把项目路径替换进 `com.example.dashboard-refresh.plist` 再装到
   `~/Library/LaunchAgents/`)。

## 注意

- `validate_data.py` 会拒绝 `generated_at` 超过 24 小时的数据,针对的是新生成的
  `data.json`,不是示例文件。
- `.env`、`credentials/`、`data/`、`backups/`、`logs/`、`dashboard/data.json`
  都在 `.gitignore` 里,不要提交。

完整说明见英文 [README.md](README.md)。
