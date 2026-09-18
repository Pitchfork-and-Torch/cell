# USB modem extension point

`cell.providers.modem.ModemProvider` is intentionally incomplete.

Planned mapping (same CLI):

| CLI | Linux (ModemManager) | Windows |
|-----|----------------------|---------|
| `status` | `mmcli -L` / `-m 0` signal | AT+CSQ on COM port |
| `send` | `mmcli -m 0 --messaging-create-sms` + `--messaging-send` | AT+CMGF=1 / AT+CMGS |
| `inbox` | `mmcli --messaging-list-sms` | AT+CMGL |
| `watch` | poll the above | poll the above |

Do not add this backend until a specific owned dongle is on the desk. Cloud PSTN is the supported path.
