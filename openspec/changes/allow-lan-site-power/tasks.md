## 1. LAN 公開中の起動・停止

- [x] 1.1 `views.py` から `PUBLIC_REASON` と LAN 公開の判定を外し、`index.html` の案内の表示を外す。LAN 公開中も POST で停止でき、ボタンが有効なことを test_site_power_views で確かめる
- [x] 1.2 CSRF トークンのない POST が 403 になり、GET が 405 になる既存のテストが通ることを確かめる

## 2. ドキュメント

- [x] 2.1 `.env.example` と `README.md` の、LAN 公開中は起動・停止が無効になるという説明を直す
