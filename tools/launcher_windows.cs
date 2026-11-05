using System;
using System.IO;
using System.Text;
using System.Diagnostics;
using System.Windows.Forms;
using System.Reflection;

[assembly: AssemblyTitle("Magazzino Profili")]
[assembly: AssemblyDescription("Avvio di Magazzino Profili senza estrazione temporanea")]
[assembly: AssemblyVersion("@VERSIONE@.0")]
[assembly: AssemblyFileVersion("@VERSIONE@.0")]

internal static class AvvioMagazzino
{
    private static string Argomento(string valore)
    {
        StringBuilder b = new StringBuilder("\"");
        int barre = 0;
        foreach (char c in valore)
        {
            if (c == '\\') { barre++; continue; }
            if (c == '"') { b.Append('\\', barre * 2 + 1); b.Append(c); barre = 0; continue; }
            b.Append('\\', barre); barre = 0; b.Append(c);
        }
        b.Append('\\', barre * 2); b.Append('"');
        return b.ToString();
    }

    [STAThread]
    private static int Main(string[] argomenti)
    {
        try
        {
            string desktop = AppDomain.CurrentDomain.BaseDirectory;
            string cartella = Path.Combine(desktop, "@CARTELLA@");
            string programma = Path.Combine(cartella, "MagazzinoProfili.exe");
            if (!File.Exists(programma))
                throw new FileNotFoundException("La cartella del programma deve restare accanto a questo eseguibile: " + cartella);
            string configurazione = Environment.GetEnvironmentVariable("MAGAZZINO_CONFIG");
            if (String.IsNullOrWhiteSpace(configurazione))
            {
                foreach (string candidato in new string[] {
                    Path.Combine(cartella, "config.toml"),
                    Path.Combine(desktop, "magazzino", "config.toml"),
                    Path.Combine(desktop, "config.toml") })
                {
                    if (File.Exists(candidato)) { configurazione = candidato; break; }
                }
            }
            ProcessStartInfo avvio = new ProcessStartInfo(programma);
            avvio.UseShellExecute = false;
            avvio.CreateNoWindow = true;
            avvio.WorkingDirectory = cartella;
            if (!String.IsNullOrWhiteSpace(configurazione))
            {
                configurazione = Path.GetFullPath(configurazione);
                avvio.EnvironmentVariables["MAGAZZINO_CONFIG"] = configurazione;
                avvio.WorkingDirectory = Path.GetDirectoryName(configurazione);
            }
            StringBuilder parametri = new StringBuilder();
            foreach (string argomento in argomenti) { if (parametri.Length > 0) parametri.Append(' '); parametri.Append(Argomento(argomento)); }
            avvio.Arguments = parametri.ToString();
            Process.Start(avvio);
            return 0;
        }
        catch (Exception errore)
        {
            MessageBox.Show("Impossibile avviare Magazzino Profili.\n\n" + errore.Message,
                "Magazzino Profili", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
