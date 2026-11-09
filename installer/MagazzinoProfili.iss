; Identita e versione provengono dalla build Python, non da valori duplicati qui.
#ifndef AppVersion
  #error AppVersion obbligatoria: usare installer\build.bat
#endif
#ifndef AppIdFisso
  #error AppIdFisso obbligatorio
#endif
#ifndef Payload
  #error Payload obbligatorio
#endif
#ifndef Output
  #error Output obbligatorio
#endif
#ifndef MutexApp
  #error MutexApp obbligatorio
#endif
#ifndef Editore
  #define Editore "Si2008"
#endif

[Setup]
AppId={#AppIdFisso}
AppName=Magazzino Profili
AppVersion={#AppVersion}
AppVerName=Magazzino Profili {#AppVersion}
AppPublisher={#Editore}
AppPublisherURL=https://github.com/Si2008/Magazzino
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#Editore}
VersionInfoProductName=Magazzino Profili
DefaultDirName={localappdata}\Programs\Magazzino Profili
DefaultGroupName=Magazzino Profili
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UsePreviousAppDir=yes
UsePreviousTasks=yes
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
DisableReadyPage=no
ShowLanguageDialog=no
WizardStyle=modern
SetupIconFile=..\icona.ico
UninstallDisplayIcon={app}\MagazzinoProfili.exe
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallDisplayName=Magazzino Profili
SetupMutex=Local\MagazzinoProfili.Setup.7FCFE24E
CloseApplications=no
RestartApplications=no
RestartIfNeededByRun=no
ChangesEnvironment=no
Compression=lzma2/fast
SolidCompression=yes
OutputDir={#Output}
OutputBaseFilename=MagazzinoProfili-{#AppVersion}-setup
InfoBeforeFile=Informazioni.txt

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; Flags: unchecked

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.toml,*.dump,*.db,*.sqlite,*.sqlite3,chiave_privata.pem,*.key"

[Icons]
Name: "{userprograms}\Magazzino Profili\Magazzino Profili"; Filename: "{app}\MagazzinoProfili.exe"; WorkingDir: "{app}"
Name: "{userprograms}\Magazzino Profili\Disinstalla Magazzino Profili"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Magazzino Profili"; Filename: "{app}\MagazzinoProfili.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MagazzinoProfili.exe"; Description: "Avvia Magazzino Profili"; Flags: nowait postinstall skipifsilent
Filename: "{app}\MagazzinoProfili.exe"; Flags: nowait; Check: RiavvioRichiesto

[Registry]
; Solo la voce di disinstallazione, creata automaticamente da [Setup].
; Nessuna associazione file, chiave Run, variabile d'ambiente o voce di altri programmi.

[UninstallDelete]
; Nessun wildcard: Inno rimuove solo i file registrati della propria installazione.
Type: dirifempty; Name: "{app}"

[Code]
const
  Identita = '{#AppIdFisso}';
  ChiaveUninstall = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppIdFisso}_is1';
  MutexRuntime = '{#MutexApp}';
var
  EliminaDati: Boolean;
  InstallazionePrecedente: String;

function RiavvioRichiesto(): Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RIAVVIA|0}') = '1');
end;

function PercorsoCanonico(P: String): String;
begin
  Result := Lowercase(RemoveBackslashUnlessRoot(ExpandFileName(P)));
end;

function Dati: String;
begin
  Result := ExpandConstant('{localappdata}\Magazzino Profili');
end;

function CartellaVuota(P: String): Boolean;
var R: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(P) + '*', R) then begin
    try
      repeat
        if (R.Name <> '.') and (R.Name <> '..') then begin
          Result := False;
          Break;
        end;
      until not FindNext(R);
    finally FindClose(R); end;
  end;
end;

function DestinazioneValida(P: String): Boolean;
var Marcatore: AnsiString; C, CD: String;
begin
  C := AddBackslash(PercorsoCanonico(P));
  CD := AddBackslash(PercorsoCanonico(Dati));
  Result := (Length(C) > 4) and (Pos(CD, C) <> 1) and (Pos(C, CD) <> 1);
  if Result and DirExists(P) and not CartellaVuota(P) then
    Result := LoadStringFromFile(AddBackslash(P) + 'installazione.json', Marcatore) and
              (Pos(Identita, String(Marcatore)) > 0);
  if Result and (InstallazionePrecedente <> '') then
    Result := PercorsoCanonico(P) = PercorsoCanonico(InstallazionePrecedente);
end;

function InitializeSetup(): Boolean;
var VersionePrecedente: String; Vecchia, Nuova: Int64;
begin
  Result := True;
  RegQueryStringValue(HKCU64, ChiaveUninstall, 'InstallLocation', InstallazionePrecedente);
  if RegQueryStringValue(HKCU64, ChiaveUninstall, 'DisplayVersion', VersionePrecedente) then begin
    if StrToVersion(VersionePrecedente, Vecchia) and StrToVersion('{#AppVersion}', Nuova) then
      if ComparePackedVersion(Vecchia, Nuova) > 0 then begin
        SuppressibleMsgBox('Una versione piu recente e gia installata. Il downgrade e stato bloccato per proteggere i dati.', mbError, MB_OK, IDOK);
        Result := False;
      end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then begin
    Result := DestinazioneValida(WizardDirValue);
    if not Result then
      MsgBox('Scegli una cartella nuova o la precedente installazione di Magazzino Profili. La cartella dati e le cartelle di altri programmi non possono essere usate. Gli aggiornamenti mantengono la cartella gia registrata.', mbError, MB_OK);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Tentativi: Integer;
begin
  Result := '';
  if not DestinazioneValida(WizardDirValue) then begin
    Result := 'Destinazione non valida: nessun file installato.';
    Exit;
  end;
  Tentativi := 0;
  while CheckForMutexes(MutexRuntime) and (Tentativi < 100) do begin
    Sleep(200);
    Tentativi := Tentativi + 1;
  end;
  if CheckForMutexes(MutexRuntime) then
    Result := 'Chiudi Magazzino Profili anche dall''area di notifica e riprova. Nessun processo viene terminato automaticamente.';
end;

function SenzaCollegamenti(P: String): Boolean;
var R: TFindRec;
begin
  Result := False;
  if not FindFirst(P, R) then Exit;
  try
    if (R.Attributes and $400) <> 0 then Exit;
  finally FindClose(R); end;
  Result := True;
  if FindFirst(AddBackslash(P) + '*', R) then begin
    try
      repeat
        if (R.Name <> '.') and (R.Name <> '..') then begin
          if (R.Attributes and $400) <> 0 then begin Result := False; Break; end;
          if (R.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            if not SenzaCollegamenti(AddBackslash(P) + R.Name) then begin Result := False; Break; end;
        end;
      until not FindNext(R);
    finally FindClose(R); end;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := not CheckForMutexes(MutexRuntime);
  if not Result then begin
    SuppressibleMsgBox('Chiudi Magazzino Profili prima di disinstallare. Nessun processo viene terminato automaticamente.', mbError, MB_OK, IDOK);
    Exit;
  end;
  EliminaDati := False;
  if not UninstallSilent and DirExists(Dati) then begin
    if MsgBox('Vuoi conservare i dati locali di Magazzino Profili per una reinstallazione?' + #13#10 + Dati + #13#10 + 'Scegli Si per conservarli (consigliato). I database PostgreSQL esterni, le cartelle condivise e i vecchi dati portabili non vengono rimossi.', mbConfirmation, MB_YESNO or MB_DEFBUTTON1) = IDNO then
      EliminaDati := MsgBox('Confermi di eliminare DEFINITIVAMENTE solo la cartella dati locali indicata, incluse immagini, commesse locali, configurazione e backup contenuti?' + #13#10 + Dati, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Marcatore: AnsiString;
begin
  if (CurUninstallStep = usPostUninstall) and EliminaDati then begin
    if CheckForMutexes(MutexRuntime) then begin
      MsgBox('Programma ancora attivo: i dati sono stati conservati.', mbInformation, MB_OK);
      Exit;
    end;
    if LoadStringFromFile(AddBackslash(Dati) + '.magazzino-profili-dati.json', Marcatore) and
       (Pos(Identita, String(Marcatore)) > 0) and SenzaCollegamenti(Dati) then begin
      if not DelTree(Dati, True, True, True) then
        MsgBox('Alcuni dati locali non sono stati rimossi. Verifica la cartella indicata.', mbInformation, MB_OK);
    end else
      MsgBox('Identita della cartella dati non verificata o presenza di collegamenti: dati conservati.', mbInformation, MB_OK);
  end;
end;
