<?php

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
  http_response_code(204);
  exit;
}

$webhookUrl = trim(file_get_contents(__DIR__ . '/.env'));

$rawData = file_get_contents('php://input');

if (strlen($rawData) > 2000) {
  http_response_code(400);
  exit;
}

$cf_ranges = [
  [ip2long('173.245.48.0'),   ip2long('173.245.63.255')],
  [ip2long('103.21.244.0'),   ip2long('103.21.247.255')],
  [ip2long('103.22.200.0'),   ip2long('103.22.203.255')],
  [ip2long('103.31.4.0'),     ip2long('103.31.7.255')],
  [ip2long('141.101.64.0'),   ip2long('141.101.127.255')],
  [ip2long('108.162.192.0'),  ip2long('108.162.255.255')],
  [ip2long('190.93.240.0'),   ip2long('190.93.255.255')],
  [ip2long('188.114.96.0'),   ip2long('188.114.127.255')],
  [ip2long('197.234.240.0'),  ip2long('197.234.243.255')],
  [ip2long('198.41.128.0'),   ip2long('198.41.255.255')],
  [ip2long('162.158.0.0'),    ip2long('162.159.255.255')],
  [ip2long('104.16.0.0'),     ip2long('104.23.255.255')],
  [ip2long('104.24.0.0'),     ip2long('104.27.255.255')],
  [ip2long('172.64.0.0'),     ip2long('172.71.255.255')],
  [ip2long('131.0.72.0'),     ip2long('131.0.75.255')]
];

$realIp = $_SERVER['REMOTE_ADDR'];
$ipLong = ip2long($realIp);
$isCF = false;

foreach ($cf_ranges as $range) {
  if ($ipLong >= $range[0] && $ipLong <= $range[1]) {
    $isCF = true;
    break;
  }
}

if ($isCF && isset($_SERVER['HTTP_CF_CONNECTING_IP'])) {
  $realIp = $_SERVER['HTTP_CF_CONNECTING_IP'];
} elseif (isset($_SERVER['HTTP_CF_CONNECTING_IP'])) {
  http_response_code(403);
  exit;
}

$key = "rate_limit_" . $realIp;

if (!apcu_add($key, time(), 10)) {
  http_response_code(429);
  exit;
}

if (!json_validate($rawData)) {
  http_response_code(400);
  exit;
}

$formData = json_decode($rawData, true);

if (!$formData) {
  http_response_code(400);
  exit;
}

$discordData = [
  "username" => "club registration",

  "embeds" => [[
    "title" => "new club registration!",
    "thumbnail" => [
      "url" => "https://m.tilley.lol/thumb.webp"
    ],
    "color" => 0xA7C080,
    "fields" => [
      ["name" => "Name", "value" => $formData['name'], "inline" => false],
      ["name" => "Email", "value" => $formData['email'], "inline" => false],
      ["name" => "Reason", "value" => $formData['reason'], "inline" => false],
      ["name" => "Grade", "value" => $formData['grade'], "inline" => false],
      ["name" => "Availability", "value" => $formData['availability'], "inline" => false],
      ["name" => "Found", "value" => $formData['found'], "inline" => false],
      ["name" => "Else", "value" => $formData['else'] ?? 'N/A', "inline" => false],
      [
        "name"   => "Metadata",
        "value"  => "IP Address: `" . $_SERVER['HTTP_CF_CONNECTING_IP'] . "`\n" .
          "User Agent: ```text\n" . str_replace('`', ' \` ', $_SERVER['HTTP_USER_AGENT']) . "\n```",
        "inline" => false
      ],
    ],
  ]]
];

$ch = curl_init($webhookUrl);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($discordData));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);

if ($httpCode < 200 || $httpCode >= 300) {
  http_response_code(500);
} else {
  http_response_code(204);
}

curl_close($ch);
