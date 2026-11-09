param([string]$Cartella)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$asTask=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
function Attendi($operazione,$tipo){
 $task=$asTask.MakeGenericMethod($tipo).Invoke($null,@($operazione));try{$task.Wait()}catch{throw $_.Exception.ToString()};return $task.Result
}
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if($null -eq $engine){throw 'Lingua OCR Windows non disponibile'}
$risultati=@()
foreach($file in Get-ChildItem -LiteralPath $Cartella -Filter '*.png'){
 $f=Attendi ([Windows.Storage.StorageFile]::GetFileFromPathAsync($file.FullName)) ([Windows.Storage.StorageFile])
 $stream=Attendi ($f.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
 try{
  $decoder=Attendi ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap=Attendi ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  try{
   $ris=Attendi ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
   $parole=@();foreach($line in $ris.Lines){foreach($w in $line.Words){$parole+=@{testo=$w.Text;x=$w.BoundingRect.X;y=$w.BoundingRect.Y;altezza=$w.BoundingRect.Height}}}
   $risultati+=@{file=$file.Name;testo=$ris.Text;parole=$parole}
  }finally{$bitmap.Dispose()}
 }finally{$stream.Dispose()}
}
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
ConvertTo-Json -InputObject @($risultati) -Depth 6 -Compress

