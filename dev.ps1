param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)
python -B tools/dev.py @Arguments
