#!/bin/bash
# Usage: bash process_moneyflow.sh < batch_N.json
# Input: JSONL (one JSON object per line): {"code":"000988","klines":["date,f52,f53,f54,f55,f56,...",...]}
# Output: INSERT OR REPLACE statements piped to sqlite3
#
# EastMoney kline format: date, main_net_amt, elg_net, lg_net, md_net, sm_net, f61, f62
# Field mapping:
#   main_net_amt = f52
#   elg_buy = max(f53,0), elg_sell = abs(min(f53,0))
#   lg_buy  = max(f54,0), lg_sell  = abs(min(f54,0))
#   md_buy  = max(f55,0), md_sell  = abs(min(f55,0))
#   sm_buy  = max(f56,0), sm_sell  = abs(min(f56,0))
#   net_mf_amt = f52+f53+f54
#   data_source = 'eastmoney'

DB=/Users/yellow/my_quant_system/stock_data.db

while IFS= read -r line; do
  code=$(echo "$line" | /usr/bin/jq -r '.code')
  echo "$line" | /usr/bin/jq -r '.klines[]' | /usr/bin/awk -F',' -v c="$code" '{
    dt=$1; f52=$2; f53=$3; f54=$4; f55=$5; f56=$6;
    ebg=(f53>0?f53:0); esl=(f53<0?-f53:0);
    lbg=(f54>0?f54:0); lsl=(f54<0?-f54:0);
    mbg=(f55>0?f55:0); msl=(f55<0?-f55:0);
    sbg=(f56>0?f56:0); ssl=(f56<0?-f56:0);
    nmf=f52+f53+f54;
    printf "INSERT OR REPLACE INTO moneyflow_daily(stock_code,date,main_net_amt,elg_buy_amt,elg_sell_amt,lg_buy_amt,lg_sell_amt,md_buy_amt,md_sell_amt,sm_buy_amt,sm_sell_amt,net_mf_amt,data_source) VALUES('\''%s'\'','\''%s'\'',%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,%.0f,'\''eastmoney'\'');\n", c,dt,f52,ebg,esl,lbg,lsl,mbg,msl,sbg,ssl,nmf;
  }'
done | /usr/bin/sqlite3 $DB
echo "Done: exit=$?"
