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
if (json_validate($rawData)) {
  $data = json_decode($rawData, true);
} else {
  http_response_code(400);
  exit;
}
$formData = json_decode($rawData, true);

if (!$formData) {
  http_response_code(400);
  exit;
}

$email = $formData['email'] ?? '';

$discordData = [
  "username" => "club registration",

  "embeds" => [[
    "title" => "new club registration!",
    "thumbnail" => [
      "url" => "https://m.tilley.lol/thumb.webp"
    ],
    "color" => 0xA7C080,
    "fields" => [
      ["name" => "Name", "value" => $formData['name'] ?? 'N/A', "inline" => false],
      ["name" => "Email", "value" => $formData['email'] ?? 'N/A', "inline" => false],
      ["name" => "Reason", "value" => $formData['reason'] ?? 'N/A', "inline" => false],
      ["name" => "Grade", "value" => $formData['grade'] ?? 'N/A', "inline" => false],
      ["name" => "Availability", "value" => $formData['availability'] ?? 'N/A', "inline" => false],
      ["name" => "Found", "value" => $formData['found'] ?? 'N/A', "inline" => false],
      ["name" => "Else", "value" => $formData['else'] ?? 'N/A', "inline" => false],
      [
        "name"   => "Metadata",
        "value"  => "IP Address: `" . $_SERVER['REMOTE_ADDR'] . "`\n" .
          "User Agent: ```text\n" . $_SERVER['HTTP_USER_AGENT'] . "\n```",
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
