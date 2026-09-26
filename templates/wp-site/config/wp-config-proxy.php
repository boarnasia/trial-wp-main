<?php
/**
 * リバースプロキシ（Caddy）配下で動かすための wp-config.php 追加設定。
 * WORDPRESS_CONFIG_EXTRA から require_once される。
 */

// プロキシが TLS を終端するため、ヘッダーで HTTPS を判定しないと is_ssl() が false になり無限リダイレクトする
if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && stripos($_SERVER['HTTP_X_FORWARDED_PROTO'], 'https') !== false) {
	$_SERVER['HTTPS'] = 'on';
}

$wp_home = getenv('WP_HOME');
if ($wp_home) {
	defined('WP_HOME') || define('WP_HOME', rtrim($wp_home, '/'));
	defined('WP_SITEURL') || define('WP_SITEURL', rtrim($wp_home, '/'));
}
unset($wp_home);
