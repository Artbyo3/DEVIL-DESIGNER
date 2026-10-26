param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)
python tools/dev.py @Arguments
