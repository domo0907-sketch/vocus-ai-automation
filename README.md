# 方格子自有文章 AI 草稿自動化

來源房間：https://vocus.cc/salon/69f0a41efd89780001eabb27/room/69f1f313293a143b79774adf

## 你會得到什麼

每天台灣時間 09:00 檢查「寵物」房間頁面目前可見的文章網址（**不是所有歷史文章**）；每次最多處理 `config.json` 中的 3 篇未處理文章；抓取正文、AI 重新整理為 Markdown 草稿，存到 `output/`；`state.json` 記錄已處理文章，以免重複扣 API 費用。**不會自動發到方格子。**

## GitHub 設置（使用新建的私人儲存庫）

1. 建立一個 **Private repository**，例如 `vocus-drafts`。
2. 解壓縮本檔，將檔案與 `.github/workflows/daily.yml` 資料夾完整上傳到 repo 根目錄。
3. GitHub → Settings → Secrets and variables → Actions → New repository secret，名稱 `OPENAI_API_KEY`，值填你自己的 OpenAI API Key。
4. GitHub → Settings → Actions → General → Workflow permissions → 選 **Read and write permissions**，儲存。
5. GitHub → Actions → Daily Vocus Drafts → Run workflow，先手動測試一次。
6. 到 `output/` 查看生成的 `.md` 草稿，到 `state.json` 查看已完成項目。
7. 測試正常後，GitHub Actions 每天約 09:00 執行（排程可能延遲，非保證準點）。

## 注意

- 執行的是已公開且你有權使用的文章；請勿用本程式繞過登入、付費牆、防機器人保護或頻率限制。
- 文章頁 HTML 改版，`main.py` 的 CSS selectors 可能要調整。本工具**尚未在真實 GitHub Actions 執行環境端到端驗證**。
- 第一版只會讀取「寵物」房間頁面 HTML 中直接找到的文章連結；不保證取得全部分頁或歷史文章。
- AI 草稿不一定適合重新發布到同一帳號，請查證商品價格、規格、實測與重複內容風險。
- 私人 repo 仍要避免放 API Key、會員資料或敏感資料在 `output`；API Key **只能放 Secret**。
- 若每日作業因被擋或無文章而失敗，查看 Actions log；不要嘗試繞過存取限制。
- 想只處理全新發表文章，可以在第一輪將現有文章網址標為已處理，再啟用每日排程。
- 修改每天草稿上限：`config.json` → `max_new_articles_per_run`。
