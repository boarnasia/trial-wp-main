"""環境の migration。

1 ファイル 1 つで mNNNN_<名前>.py に置き、VERSION・DESCRIPTION・REQUIRES_SUDO・DESTRUCTIVE・LOSES と
up(ctx) を定義する。バージョン 1 は基準なのでファイルを持たず、最初の migration は m0002 になる。
up は途中で失敗して再実行されても結果が同じになるよう、冪等に書く。
"""
