//+------------------------------------------------------------------+
//|                                          AlphaScalpCopier.mq5     |
//|            Client de copie AlphaScalp — bêta, comptes DÉMO        |
//+------------------------------------------------------------------+
//  Interroge le serveur AlphaScalp et reproduit ses trades sur CE compte.
//
//  CE QU'IL FAIT
//    - relève les nouveaux signaux via un curseur (id croissant) : aucun
//      trade n'est rejoué deux fois, même après un redémarrage ;
//    - calcule SA PROPRE taille de position depuis le SL et un % de risque
//      choisi ici. Il ne copie PAS le volume du maître, qui dépend d'un
//      capital différent — c'est ce qui rend la copie proportionnelle ;
//    - ferme la position correspondante quand le maître ferme.
//
//  CE QU'IL NE FAIT PAS
//    - il ne touche à aucune position ouverte à la main : il ne gère que
//      celles qu'il a lui-même ouvertes, reconnues par leur numéro magique ;
//    - il n'envoie aucune donnée personnelle : seule la clé d'API circule ;
//    - il ne modifie aucun réglage du terminal.
//
//  ⚠️ DEUX POINTS À CONNAÎTRE AVANT DE LANCER
//    1. MetaTrader exige une AUTORISATION MANUELLE pour joindre un serveur :
//       Outils > Options > Expert Advisors > cocher « Autoriser les WebRequest »
//       et ajouter l'adresse du serveur à la liste. Sans ça, rien ne
//       fonctionnera — l'EA le détecte et le dit clairement au démarrage.
//    2. MT5 sur téléphone N'EXÉCUTE PAS les Expert Advisors (limite de
//       MetaQuotes, Android comme iOS). Il faut un PC allumé ou un VPS.
//
//  SÉCURITÉ : par défaut l'EA REFUSE de démarrer sur un compte réel. La bêta
//  se fait sur démo. Ce garde-fou se désactive volontairement (AutoriserCompteReel),
//  jamais par accident.
//+------------------------------------------------------------------+
#property copyright "AlphaScalp"
#property link      "https://alphascalp.onrender.com"
#property version   "1.12"
#property strict
// [02/08] La version était écrite en dur À DEUX ENDROITS (ici et dans le corps
// du rapport d'état). Résultat : la copie installée sur le PC de test datait du
// 31/07 — sans les gardes anti-rejeu et anti-signal-périmé — et s'annonçait
// « 1.00 », exactement comme la version distribuée. Rien ne permettait de voir
// l'écart. Une seule source de vérité désormais ; le numéro monte à chaque
// changement de comportement.
//   1.00 (31/07) — première version bêta
//   1.10 (01/08) — garde anti-rejeu au premier lancement, refus des signaux
//                  périmés (AgeMaxSignalSec), alertes visibles sur échec d'init
//   1.11 (03/08) — remise à zéro du serveur : on reprend au DÉBUT de sa
//                  nouvelle liste. Se caler sur son dernier id sautait les
//                  signaux déjà présents, dont pouvait faire partie une
//                  fermeture — le suiveur restait alors ouvert.
//   1.12 (03/08) — délais réseau réduits et bornés par la période du timer.
//                  L'EA pouvait bloquer plus longtemps que son propre cycle :
//                  MetaTrader paraissait figé.
#define COPIEUR_VERSION "1.12"

// [03/08] DÉLAIS RÉSEAU — à ne pas augmenter sans lire ceci.
//
// WebRequest est SYNCHRONE : il bloque le fil d'exécution de l'EA pendant
// toute l'attente, et avec lui la charte. Les valeurs précédentes étaient
// 15 s pour la relève et 10 s pour le rapport d'état, alors que le timer se
// déclenche toutes les 10 s. Un serveur lent suffisait donc à ce que l'EA
// bloque PLUS LONGTEMPS que son propre cycle : les événements s'empilaient et
// MetaTrader devenait incliquable. Constaté sur le poste de test le 03/08.
//
// Règle : période du timer >= somme des délais + marge. Elle est calculée à
// partir de ces constantes dans OnInit, elle n'est pas laissée au hasard.
//
// Un serveur qui met plus de 5 s à répondre est de toute façon indisponible
// pour nous : on réessaie au cycle suivant, ce qui coûte moins cher que
// d'attendre.
#define DELAI_SIGNAUX_MS 5000
#define DELAI_ETAT_MS    3000
#property description "Copie les trades AlphaScalp sur ce compte. Bêta : comptes démo."

#include <Trade\Trade.mqh>

//--- Réglages -------------------------------------------------------
input group "Connexion"
input string  AdresseServeur      = "https://alphascalp.onrender.com"; // Adresse du serveur
input string  CleApi              = "";        // Ta clé bêta (as_...)
input int     IntervalleSecondes  = 10;        // Fréquence de relève (secondes)

input group "Risque"
input double  RisqueParTrade      = 1.0;       // Risque par trade (% du capital)
input double  LotMaximum          = 1.0;       // Plafond de volume par trade
input int     PositionsMaximum    = 3;         // Positions simultanées maximum

input group "Symboles"
input string  SuffixeSymbole      = "";        // Suffixe broker (ex: ".r", "m", "#")
input string  PrefixeSymbole      = "";        // Préfixe broker si besoin

input group "Sécurité"
input bool    AutoriserCompteReel = false;     // DANGER : autoriser un compte réel
input int     GlissementPoints    = 30;        // Glissement toléré (points)
input long    NumeroMagique       = 770777;    // Identifie NOS positions
input int     AgeMaxSignalSec     = 300;       // Âge max d'un signal pour être joué (s)

//--- État interne ---------------------------------------------------
CTrade   trade;
long     curseur          = -1;      // dernier id de signal traité
bool     enPause          = false;   // clé inactive côté serveur
bool     initialisationOk = false;
string   cheminCurseur;              // fichier de persistance du curseur
datetime dernierAvertissement = 0;

//+------------------------------------------------------------------+
//| Journalisation                                                    |
//+------------------------------------------------------------------+
void Info(string m)    { Print("[AlphaScalp] ", m); }
void Alerte(string m)  { Print("[AlphaScalp] /!\\ ", m); }

//+------------------------------------------------------------------+
//| Extraction JSON minimale.                                         |
//| On n'embarque pas d'analyseur JSON complet : le format renvoyé par |
//| le serveur est connu, stable et plat. Un analyseur générique       |
//| ajouterait des centaines de lignes et autant d'occasions de bug    |
//| pour un bénéfice nul ici.                                          |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Échappe une chaîne pour l'insérer dans du JSON.                    |
//| Un nom de courtier contenant un guillemet casserait le corps de la |
//| requête, et le serveur rejetterait le rapport sans qu'on sache     |
//| pourquoi.                                                          |
//+------------------------------------------------------------------+
string EchapperJson(string s)
  {
   string r = "";
   for(int i = 0; i < StringLen(s); i++)
     {
      ushort c = StringGetCharacter(s, i);
      if(c == '"' || c == '\\') r += "_";     // on remplace, plus simple et sûr
      else if(c < 32)            r += " ";
      else                       r += ShortToString(c);
     }
   return r;
  }

string JsonTexte(string json, string cle, string defaut = "")
  {
   string motif = "\"" + cle + "\":";
   int p = StringFind(json, motif);
   if(p < 0) return defaut;
   p += StringLen(motif);
   while(p < StringLen(json) && StringGetCharacter(json, p) == ' ') p++;
   if(p >= StringLen(json)) return defaut;
   if(StringGetCharacter(json, p) == '"')          // valeur entre guillemets
     {
      p++;
      int fin = StringFind(json, "\"", p);
      if(fin < 0) return defaut;
      return StringSubstr(json, p, fin - p);
     }
   int fin = p;                                     // nombre, true/false, null
   while(fin < StringLen(json))
     {
      ushort c = StringGetCharacter(json, fin);
      if(c == ',' || c == '}' || c == ']') break;
      fin++;
     }
   string v = StringSubstr(json, p, fin - p);
   StringTrimLeft(v); StringTrimRight(v);
   if(v == "null") return defaut;
   return v;
  }

double JsonNombre(string json, string cle, double defaut = 0.0)
  {
   string v = JsonTexte(json, cle, "");
   if(v == "") return defaut;
   return StringToDouble(v);
  }

//+------------------------------------------------------------------+
//| Découpe le tableau "signals":[ {...}, {...} ] en objets            |
//+------------------------------------------------------------------+
int DecouperSignaux(string json, string &objets[])
  {
   ArrayResize(objets, 0);
   int debutTableau = StringFind(json, "\"signals\"");
   if(debutTableau < 0) return 0;
   int p = StringFind(json, "[", debutTableau);
   if(p < 0) return 0;

   int profondeur = 0, depart = -1, n = 0;
   bool dansTexte = false;
   for(int i = p; i < StringLen(json); i++)
     {
      ushort c = StringGetCharacter(json, i);
      if(c == '"' && (i == 0 || StringGetCharacter(json, i - 1) != '\\'))
         dansTexte = !dansTexte;
      if(dansTexte) continue;
      if(c == '{') { if(profondeur == 0) depart = i; profondeur++; }
      else if(c == '}')
        {
         profondeur--;
         if(profondeur == 0 && depart >= 0)
           {
            n++;
            ArrayResize(objets, n);
            objets[n - 1] = StringSubstr(json, depart, i - depart + 1);
            depart = -1;
           }
        }
      else if(c == ']' && profondeur == 0) break;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| Requête HTTP GET avec la clé d'API                                 |
//| Renvoie le code HTTP ; -1 = échec réseau ou URL non autorisée.     |
//+------------------------------------------------------------------+
int HttpGet(string url, string &reponse)
  {
   char   corps[], resultat[];
   string entetesRecus;
   string entetes = "X-API-Key: " + CleApi + "\r\n";
   ResetLastError();
   int code = WebRequest("GET", url, entetes, DELAI_SIGNAUX_MS, corps, resultat, entetesRecus);
   if(code == -1)
     {
      int err = GetLastError();
      reponse = "";
      if(err == 4014 || err == 5203)   // URL absente de la liste autorisée
         Alerte("Adresse NON AUTORISÉE dans MetaTrader. Outils > Options > "
                "Expert Advisors > cocher « Autoriser les WebRequest » et "
                "ajouter : " + AdresseServeur);
      else
         Alerte("Échec réseau (erreur " + IntegerToString(err) + "). "
                "Connexion Internet ? Serveur en veille ?");
      return -1;
     }
   reponse = CharArrayToString(resultat, 0, WHOLE_ARRAY, CP_UTF8);
   return code;
  }

//+------------------------------------------------------------------+
//| Rapport d'état au serveur.                                        |
//|                                                                    |
//| Sans lui, un suiveur dont le copieur ne trouve pas ses symboles ou |
//| refuse tous ses trades reste INVISIBLE : on l'apprend s'il se      |
//| plaint. Avec plusieurs testeurs chez des courtiers différents,     |
//| c'est là que se perd le plus de temps.                             |
//|                                                                    |
//| N'envoie QUE du diagnostic : version, courtier, type de compte,    |
//| dernier problème. Aucun solde, aucune position, aucun résultat —   |
//| le dépannage n'en a pas besoin.                                    |
//+------------------------------------------------------------------+
string dernierProbleme = "";
datetime dernierRapport = 0;

void RapporterEtat(string probleme = "")
  {
   // [03/08] On compare AVANT d'écraser. L'ancienne version affectait
   // dernierProbleme dès la première ligne, ce qui rendait toute comparaison
   // ultérieure vraie par construction — le garde-fou n'aurait rien gardé.
   bool memeProbleme = (probleme != "" && probleme == dernierProbleme);
   if(probleme != "") dernierProbleme = probleme;

   if(dernierRapport > 0)
     {
      // Au plus un envoi toutes les 15 min quand tout va bien : on ne veut pas
      // transformer un diagnostic en source de trafic.
      if(probleme == "" && TimeCurrent() - dernierRapport < 900) return;
      // [03/08] Et au plus un envoi toutes les 5 min pour un problème IDENTIQUE.
      // Avant, un problème était toujours envoyé. Or « symbole introuvable » se
      // déclenche une fois PAR SIGNAL : à la reprise d'une liste, c'était autant
      // d'envois bloquants de plusieurs secondes, à la chaîne. Le remède au
      // silence ne doit pas devenir la cause du blocage.
      if(memeProbleme && TimeCurrent() - dernierRapport < 300) return;
     }
   dernierRapport = TimeCurrent();

   string courtier = AccountInfoString(ACCOUNT_COMPANY);
   bool demo = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE)
               == ACCOUNT_TRADE_MODE_DEMO;
   string corps = StringFormat(
      "{\"version\":\"%s\",\"courtier\":\"%s\",\"compte\":\"%s\",\"probleme\":\"%s\"}",
      COPIEUR_VERSION, EchapperJson(courtier), (demo ? "demo" : "reel"),
      EchapperJson(dernierProbleme));

   char donnees[], resultat[];
   StringToCharArray(corps, donnees, 0, StringLen(corps), CP_UTF8);
   ArrayResize(donnees, StringLen(corps));   // sans le zéro terminal
   string entetesRecus;
   string entetes = "Content-Type: application/json\r\n"
                    "X-API-Key: " + CleApi + "\r\n";
   ResetLastError();
   // Échec silencieux volontaire : un rapport perdu ne doit surtout pas
   // perturber la copie, qui est la seule chose qui compte ici.
   WebRequest("POST", AdresseServeur + "/api/client/etat", entetes, DELAI_ETAT_MS,
              donnees, resultat, entetesRecus);
  }

//+------------------------------------------------------------------+
//| Curseur : persisté sur disque pour survivre à un redémarrage       |
//| (sans ça, l'EA rejouerait d'anciens signaux au relancement)        |
//+------------------------------------------------------------------+
void SauverCurseur()
  {
   int f = FileOpen(cheminCurseur, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return;
   FileWriteString(f, IntegerToString(curseur));
   FileClose(f);
  }

bool ChargerCurseur()
  {
   if(!FileIsExist(cheminCurseur)) return false;
   int f = FileOpen(cheminCurseur, FILE_READ | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return false;
   string s = FileReadString(f);
   FileClose(f);
   long v = (long)StringToInteger(s);
   if(v <= 0) return false;
   curseur = v;
   return true;
  }

//+------------------------------------------------------------------+
//| Nom du symbole chez CE broker (suffixes/préfixes varient)          |
//+------------------------------------------------------------------+
string SymboleLocal(string symboleMaitre)
  {
   string s = PrefixeSymbole + symboleMaitre + SuffixeSymbole;
   if(SymbolSelect(s, true)) return s;
   if(SymbolSelect(symboleMaitre, true))     // repli : nom brut
     {
      return symboleMaitre;
     }
   return "";
  }

//+------------------------------------------------------------------+
//| Volume calculé depuis le SL et le % de risque.                     |
//| On NE copie PAS le volume du maître : son capital est différent.   |
//| Renvoie 0 si le calcul est impossible ou dépasse les bornes.       |
//+------------------------------------------------------------------+
double CalculerVolume(string symbole, double prix, double sl)
  {
   if(sl <= 0.0 || prix <= 0.0) return 0.0;
   double distance = MathAbs(prix - sl);
   if(distance <= 0.0) return 0.0;

   double capital = AccountInfoDouble(ACCOUNT_EQUITY);
   double montantRisque = capital * RisqueParTrade / 100.0;

   // Perte pour 1 lot si le SL est touché, calculée par le terminal :
   // c'est la seule méthode fiable tous symboles confondus (indices, FX,
   // métaux ont des valeurs de tick très différentes).
   double perteUnLot = 0.0;
   if(!OrderCalcProfit(ORDER_TYPE_BUY, symbole, 1.0, prix, prix - distance, perteUnLot))
      return 0.0;
   perteUnLot = MathAbs(perteUnLot);
   if(perteUnLot <= 0.0) return 0.0;

   double volume = montantRisque / perteUnLot;

   double vmin = SymbolInfoDouble(symbole, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(symbole, SYMBOL_VOLUME_MAX);
   double pas  = SymbolInfoDouble(symbole, SYMBOL_VOLUME_STEP);
   if(pas > 0.0) volume = MathFloor(volume / pas) * pas;
   if(volume < vmin) volume = vmin;
   if(volume > vmax) volume = vmax;
   if(volume > LotMaximum) volume = LotMaximum;

   // Garde-fou : au volume minimum du broker, la perte peut DÉPASSER le
   // risque voulu (typiquement sur les indices, lot mini 0.1). Dans ce cas
   // on n'ouvre pas — mieux vaut un trade manqué qu'un risque non voulu.
   double perteReelle = perteUnLot * volume;
   if(perteReelle > montantRisque * 1.25)
     {
      Alerte(StringFormat("%s ignoré : au volume minimum %.2f la perte serait "
                          "de %.2f alors que ton risque cible est %.2f. "
                          "Symbole trop gros pour ce capital.",
                          symbole, volume, perteReelle, montantRisque));
      return 0.0;
     }
   return volume;
  }

//+------------------------------------------------------------------+
//| Nos positions ouvertes (numéro magique)                            |
//+------------------------------------------------------------------+
int NosPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == NumeroMagique) n++;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| CORRESPONDANCE trade du maître -> notre ticket local.              |
//|                                                                    |
//| On stockait cet identifiant dans le COMMENTAIRE de l'ordre. C'est  |
//| fragile : beaucoup de brokers tronquent le commentaire, certains   |
//| l'écrasent purement et simplement (ajout de "[sl]", "from #123"…). |
//| Le jour où le maître ferme, on ne retrouverait plus la position et |
//| elle resterait ouverte jusqu'à son SL — en silence.                |
//| On tient donc notre propre table, persistée sur disque pour        |
//| survivre aux redémarrages. Le commentaire reste un repli.          |
//+------------------------------------------------------------------+
string mapRefs[];
ulong  mapTickets[];
string cheminMap;

void MapSauver()
  {
   int f = FileOpen(cheminMap, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return;
   for(int i = 0; i < ArraySize(mapRefs); i++)
      FileWriteString(f, mapRefs[i] + "=" + IntegerToString((long)mapTickets[i]) + "\n");
   FileClose(f);
  }

void MapCharger()
  {
   ArrayResize(mapRefs, 0);
   ArrayResize(mapTickets, 0);
   if(!FileIsExist(cheminMap)) return;
   int f = FileOpen(cheminMap, FILE_READ | FILE_TXT | FILE_ANSI);
   if(f == INVALID_HANDLE) return;
   while(!FileIsEnding(f))
     {
      string ligne = FileReadString(f);
      StringTrimLeft(ligne); StringTrimRight(ligne);
      int p = StringFind(ligne, "=");
      if(p <= 0) continue;
      int n = ArraySize(mapRefs) + 1;
      ArrayResize(mapRefs, n);
      ArrayResize(mapTickets, n);
      mapRefs[n - 1]    = StringSubstr(ligne, 0, p);
      mapTickets[n - 1] = (ulong)StringToInteger(StringSubstr(ligne, p + 1));
     }
   FileClose(f);
  }

void MapAjouter(string ref, ulong ticket)
  {
   int n = ArraySize(mapRefs) + 1;
   ArrayResize(mapRefs, n);
   ArrayResize(mapTickets, n);
   mapRefs[n - 1]    = ref;
   mapTickets[n - 1] = ticket;
   MapSauver();
  }

//--- Purge les entrées dont la position n'existe plus : sans ça le
//--- fichier grossirait indéfiniment au fil des trades.
void MapNettoyer()
  {
   // Compactage EN PLACE : ArrayCopy est capricieux sur les tableaux de
   // chaînes en MQL5, on ne s'y fie pas. On décale les entrées vivantes
   // vers le début, puis on tronque.
   int total = ArraySize(mapRefs);
   int garde = 0;
   for(int i = 0; i < total; i++)
     {
      if(!PositionSelectByTicket(mapTickets[i])) continue;
      if(garde != i)
        {
         mapRefs[garde]    = mapRefs[i];
         mapTickets[garde] = mapTickets[i];
        }
      garde++;
     }
   if(garde != total)
     {
      ArrayResize(mapRefs, garde);
      ArrayResize(mapTickets, garde);
      MapSauver();
     }
  }

ulong TrouverPosition(string refMaitre)
  {
   //--- 1) notre table (fiable)
   for(int i = 0; i < ArraySize(mapRefs); i++)
      if(mapRefs[i] == refMaitre && PositionSelectByTicket(mapTickets[i]))
         if(PositionGetInteger(POSITION_MAGIC) == NumeroMagique)
            return mapTickets[i];

   //--- 2) repli par commentaire, si le broker l'a préservé
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
      string c = PositionGetString(POSITION_COMMENT);
      if(StringFind(c, refMaitre) >= 0) return t;
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| Traite un signal                                                   |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Âge d'un signal, en secondes. -1 si la date est illisible.          |
//|                                                                    |
//| [01/08] Le serveur envoie created_at depuis toujours ; personne ne  |
//| le lisait. Consequence : un terminal eteint quelques heures rejouait|
//| a son retour TOUS les signaux manques — le curseur est persiste, il |
//| redemande donc tout ce qui a suivi. Concretement, un testeur qui    |
//| eteint son PC la nuit voyait le copieur ouvrir au matin les entrees |
//| de la nuit, au prix du matin, avec des SL/TP calcules pour des      |
//| niveaux qui n existaient plus.                                      |
//|                                                                    |
//| C est le meme defaut que le rejeu d historique corrige le 31/07,    |
//| mais par un autre chemin : celui-la passait par un curseur perdu,   |
//| celui-ci par un curseur parfaitement valide. Fermer une porte ne    |
//| ferme pas l autre.                                                  |
//|                                                                    |
//| created_at est en UTC (format 2026-08-01T10:30:00Z), on compare     |
//| donc a TimeGMT() et non a l heure du courtier.                      |
//+------------------------------------------------------------------+
int AgeSignalSecondes(string obj)
  {
   string iso = JsonTexte(obj, "created_at");
   if(StringLen(iso) < 19) return -1;
   // "2026-08-01T10:30:00Z" -> "2026.08.01 10:30:00", seul format lu par MQL5
   string s = StringSubstr(iso, 0, 19);
   StringReplace(s, "-", ".");
   StringReplace(s, "T", " ");
   datetime emis = StringToTime(s);
   if(emis <= 0) return -1;
   return (int)(TimeGMT() - emis);
  }

void TraiterSignal(string obj)
  {
   string action    = JsonTexte(obj, "action");
   string refMaitre = JsonTexte(obj, "ref_id");
   string symMaitre = JsonTexte(obj, "symbol");
   string direction = JsonTexte(obj, "direction");
   double prix      = JsonNombre(obj, "price");
   double sl        = JsonNombre(obj, "sl");
   double tp        = JsonNombre(obj, "tp");

   if(refMaitre == "" || symMaitre == "") return;

   string symbole = SymboleLocal(symMaitre);
   if(symbole == "")
     {
      Alerte("Symbole " + symMaitre + " introuvable chez ton broker. "
             "Renseigne SuffixeSymbole (ex: \".r\", \"m\") dans les réglages.");
      RapporterEtat("symbole introuvable : " + symMaitre);
      return;
     }

   //--- FERMETURE -------------------------------------------------
   if(action == "close")
     {
      ulong ticket = TrouverPosition(refMaitre);
      if(ticket == 0) return;          // déjà fermée (SL/TP) : rien à faire
      if(trade.PositionClose(ticket, GlissementPoints))
         Info("Fermé " + symbole + " (maître " + refMaitre + ")");
      else
         Alerte("Échec fermeture " + symbole + " : " + trade.ResultRetcodeDescription());
      return;
     }

   if(action != "open") return;

   //--- OUVERTURE -------------------------------------------------
   if(enPause) return;                 // clé inactive : aucune entrée

   // Un signal perime ne se joue PAS. Le prix a bouge, le SL et le TP ont ete
   // calcules pour un niveau qui n existe plus : on n ouvrirait pas le meme
   // trade, on en ouvrirait un autre, moins bon, en croyant copier.
   // On le DIT : un refus silencieux ferait croire a une panne.
   int age = AgeSignalSecondes(obj);
   if(age > AgeMaxSignalSec)
     {
      Alerte(StringFormat("Signal %s ignore : emis il y a %d min, trop ancien "
                          "(limite %d min). Ton terminal etait probablement "
                          "eteint. Ce n est pas une panne — le prix a bouge "
                          "depuis, copier maintenant ouvrirait un autre trade.",
                          symMaitre, age / 60, AgeMaxSignalSec / 60));
      return;
     }
   if(age < 0)
     {
      // Date illisible : on ne sait pas. On refuse, comme partout ailleurs.
      Alerte("Signal " + symMaitre + " ignore : date d emission illisible.");
      return;
     }

   if(TrouverPosition(refMaitre) != 0) return;   // déjà copié (anti-doublon)
   if(NosPositions() >= PositionsMaximum)
     {
      Alerte("Plafond de " + IntegerToString(PositionsMaximum) +
             " positions atteint — " + symbole + " ignoré.");
      return;
     }

   bool achat = (direction == "BUY");
   double prixCourant = achat ? SymbolInfoDouble(symbole, SYMBOL_ASK)
                              : SymbolInfoDouble(symbole, SYMBOL_BID);
   if(prixCourant <= 0.0) { Alerte("Pas de cotation sur " + symbole); return; }

   // Le volume se calcule sur le prix ACTUEL, pas celui du maître : entre
   // son entrée et la nôtre le marché a bougé, et c'est notre risque réel
   // qui doit être respecté.
   double slLocal = sl;
   if(slLocal > 0.0 && prix > 0.0)
     {
      double distance = MathAbs(prix - sl);
      slLocal = achat ? prixCourant - distance : prixCourant + distance;
     }
   double tpLocal = tp;
   if(tpLocal > 0.0 && prix > 0.0)
     {
      double distance = MathAbs(tp - prix);
      tpLocal = achat ? prixCourant + distance : prixCourant - distance;
     }

   double volume = CalculerVolume(symbole, prixCourant, slLocal);
   if(volume <= 0.0) return;           // message déjà émis

   int digits = (int)SymbolInfoInteger(symbole, SYMBOL_DIGITS);
   slLocal = NormalizeDouble(slLocal, digits);
   tpLocal = NormalizeDouble(tpLocal, digits);

   trade.SetExpertMagicNumber(NumeroMagique);
   trade.SetDeviationInPoints(GlissementPoints);

   bool ok = achat
             ? trade.Buy(volume, symbole, 0.0, slLocal, tpLocal, refMaitre)
             : trade.Sell(volume, symbole, 0.0, slLocal, tpLocal, refMaitre);

   if(ok)
     {
      // On enregistre la correspondance AVANT tout le reste : c'est elle qui
      // permettra de fermer cette position quand le maître fermera.
      ulong ticket = trade.ResultOrder();
      if(ticket > 0)
        {
         // ResultOrder() renvoie le n° d'ORDRE ; la position porte le même
         // identifiant une fois l'ordre exécuté au marché.
         if(PositionSelectByTicket(ticket))
            MapAjouter(refMaitre, ticket);
         else
           {
            // Repli : on retrouve la position fraîchement ouverte sur ce
            // symbole avec notre numéro magique.
            for(int i = PositionsTotal() - 1; i >= 0; i--)
              {
               ulong t = PositionGetTicket(i);
               if(t == 0) continue;
               if(PositionGetInteger(POSITION_MAGIC) != NumeroMagique) continue;
               if(PositionGetString(POSITION_SYMBOL) != symbole) continue;
               MapAjouter(refMaitre, t);
               break;
              }
           }
        }
      Info(StringFormat("%s %s %.2f lot | SL %.*f | TP %.*f (maître %s)",
                        direction, symbole, volume, digits, slLocal, digits,
                        tpLocal, refMaitre));
     }
   else
      Alerte("Échec ouverture " + symbole + " : " + trade.ResultRetcodeDescription());
  }

//+------------------------------------------------------------------+
//| Relève et traitement                                               |
//+------------------------------------------------------------------+
void Relever()
  {
   string reponse;

   // [31/07] GARDE-FOU : ne JAMAIS relever avec un curseur non etabli.
   //
   // Avant, quand /api/status echouait au demarrage, on posait curseur = 0.
   // La requete devenait alors ?since=0, c'est-a-dire "donne-moi TOUT
   // l'historique" -- exactement ce que le demarrage cherchait a eviter.
   // L'EA ouvrait des positions sur des signaux vieux de plusieurs jours,
   // avec des SL/TP calcules pour des prix qui n'existent plus.
   //
   // Et le scenario n'avait rien de rare : oublier l'autorisation WebRequest
   // est l'erreur numero un, et le reveil a froid de l'hebergeur gratuit
   // prend 10 a 50 secondes. Dans les deux cas le premier appel echoue, le
   // testeur corrige, et le cycle suivant rejouait l'historique.
   //
   // curseur < 0 signifie desormais "pas encore etabli" : on refait
   // /api/status et on ne traite AUCUN signal ce tour-ci.
   if(curseur < 0)
     {
      string r0;
      int c0 = HttpGet(AdresseServeur + "/api/status", r0);
      if(c0 != 200)
        {
         // Un echec ici doit rester AUDIBLE : sans ca l'EA reessaierait
         // indefiniment en silence, et le testeur croirait que ca tourne.
         if((c0 == 401 || c0 == 404) &&
            TimeCurrent() - dernierAvertissement > 300)
           {
            Alerte("Cle refusee (HTTP " + IntegerToString(c0) + "). Soit "
                   "CleApi comporte une faute, soit le serveur a ete "
                   "reinitialise. Recupere la meme cle sur " + AdresseServeur +
                   "/rejoindre (rubrique cle perdue), puis demande la "
                   "reactivation. Rien a reinstaller.");
            dernierAvertissement = TimeCurrent();
           }
         return;                        // toujours injoignable : on reessaiera
        }
      curseur = (long)JsonNombre(r0, "latest_signal_id", 0);
      SauverCurseur();
      Info("Curseur etabli au signal n°" + IntegerToString(curseur) +
           " (l'historique n'est pas rejoue).");
      return;                           // on repart proprement au prochain tour
     }

   string url = AdresseServeur + "/api/signals?since=" + IntegerToString(curseur);
   int code = HttpGet(url, reponse);

   if(code == -1) return;                    // message déjà émis

   if(code == 403)
     {
      if(!enPause)
        {
         enPause = true;
         Alerte("Clé INACTIVE côté serveur : plus aucune nouvelle entrée. "
                "Les positions déjà ouvertes restent gérées par leur SL/TP.");
         // Une mise en pause silencieuse ferait croire a une panne. On le dit.
         Alert("AlphaScalp : ton accès est en PAUSE. Aucune nouvelle position "
               "ne sera ouverte. Les positions en cours gardent leur stop.");
        }
      return;
     }
   if(code == 401 || code == 404)
     {
      // [31/07] Le message disait seulement "verifie CleApi". C'est le
      // mauvais diagnostic dans le cas le PLUS frequent : l'hebergement
      // gratuit repart sur un disque vide apres une mise en veille, la base
      // est reinitialisee, et le serveur ne reconnait plus une cle pourtant
      // correcte. Le testeur verifiait sa cle, la trouvait juste, et restait
      // bloque. On nomme les deux causes et on donne la sortie.
      if(TimeCurrent() - dernierAvertissement > 300)
        {
         Alerte("Cle refusee (HTTP " + IntegerToString(code) + "). Deux causes "
                "possibles : soit CleApi comporte une faute, soit le serveur a "
                "ete reinitialise et a oublie les inscriptions.");
         Alerte("Dans le doute, va sur " + AdresseServeur + "/rejoindre , "
                "clique sur 'cle perdue' et donne email + date de naissance : "
                "tu recuperes LA MEME cle. Previens ensuite pour reactivation. "
                "Rien a reinstaller, l'EA reprendra tout seul.");
         dernierAvertissement = TimeCurrent();
        }
      return;
     }
   if(code != 200)
     {
      if(TimeCurrent() - dernierAvertissement > 300)
        {
         Alerte("Réponse inattendue du serveur : HTTP " + IntegerToString(code));
         dernierAvertissement = TimeCurrent();
        }
      return;
     }

   if(enPause)
     {
      enPause = false;
      Info("Clé réactivée — reprise des entrées.");
      // Alert() ouvre une fenetre et joue un son : le testeur est prevenu
      // MEME s'il ne regarde pas le journal. Sans ca, l'activation de sa cle
      // ne lui parvenait par AUCUN canal -- ni email, ni message : on ne
      // dispose que de son terminal pour l'atteindre.
      Alert("AlphaScalp : ton accès est ACTIVÉ. La copie démarre, "
            "tu n'as plus rien à faire.");
     }

   //--- Le serveur est-il reparti de zéro ? --------------------------------
   // La base du serveur est éphémère : à son redémarrage la table repart vide
   // et les identifiants recommencent à 1. Sans ce contrôle, notre curseur
   // (disons 42) serait à jamais devant le dernier signal existant (disons 3)
   // et on ne recevrait PLUS RIEN — sans erreur, sans message, définitivement.
   long dernier = (long)JsonNombre(reponse, "latest", -1);
   if(dernier >= 0 && dernier < curseur)
     {
      // [03/08] On repart de 0, PAS de `dernier`.
      //
      // Le recalage sur `dernier` sautait tout ce que la nouvelle table
      // contenait déjà. Déroulé : le serveur redémarre, le maître clôture un
      // trade cinq secondes plus tard (ce close devient le n°1), on relève
      // cinq secondes après, on voit latest=1, on se cale sur 1 — et on ne
      // demande plus que les signaux AU-DELÀ de 1. La fermeture, c'était le
      // n°1. Le suiveur restait donc ouvert alors que le maître était sorti :
      // précisément la divergence que tout ce fichier cherche à empêcher.
      //
      // Repartir de 0 est sûr, parce que rien de ce qui est rejoué n'agit à
      // tort : une fermeture dont on n'a pas la position ne fait rien
      // (TrouverPosition renvoie 0), une ouverture qu'on détient déjà est
      // écartée par l'anti-doublon sur ref_id, et une ouverture périmée est
      // refusée par le garde d'ancienneté (AgeMaxSignalSec). Ne restent que
      // les signaux qu'on avait réellement manqués — ceux qu'on veut.
      //
      // La table ne contient de toute façon que ce qui a été émis DEPUIS le
      // redémarrage : le rejeu est court par construction.
      Alerte(StringFormat("Le serveur est reparti de zéro (son dernier signal "
                          "est le n°%I64d, nous en étions au n°%I64d). "
                          "Reprise depuis le début de sa nouvelle liste — "
                          "aucune action de ta part.",
                          dernier, curseur));
      curseur = 0;
      SauverCurseur();
     }

   string objets[];
   int n = DecouperSignaux(reponse, objets);
   if(n <= 0) return;

   for(int i = 0; i < n; i++)
     {
      long id = (long)JsonNombre(objets[i], "id", 0);
      TraiterSignal(objets[i]);
      // Le curseur avance MÊME si le trade a été refusé (symbole absent,
      // plafond atteint...). Sinon le même signal serait retenté sans fin.
      if(id > curseur) { curseur = id; SauverCurseur(); }
     }
  }

//+------------------------------------------------------------------+
//| Initialisation                                                     |
//+------------------------------------------------------------------+
int OnInit()
  {
   Info("=== AlphaScalp Copier v" + COPIEUR_VERSION + " ===");

   //--- Garde-fou compte réel -------------------------------------
   ENUM_ACCOUNT_TRADE_MODE mode =
      (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode != ACCOUNT_TRADE_MODE_DEMO && !AutoriserCompteReel)
     {
      Alerte("COMPTE NON DÉMO détecté — démarrage REFUSÉ.");
      Alerte("La bêta AlphaScalp se fait sur compte de démonstration.");
      Alerte("Pour passer outre en connaissance de cause : "
             "AutoriserCompteReel = true.");
      Alert("AlphaScalp : ce compte n est pas un compte de DEMONSTRATION. "
            "Le copieur ne demarre pas. La beta se fait sur demo.");
      return INIT_FAILED;
     }
   if(mode != ACCOUNT_TRADE_MODE_DEMO)
      Alerte("!!! COMPTE RÉEL — de l'argent réel est engagé à chaque trade !!!");

   //--- Réglages obligatoires --------------------------------------
   if(StringLen(CleApi) < 8)
     {
      Alerte("Clé d'API manquante. Colle ta clé bêta (as_...) dans CleApi.");
      Alert("AlphaScalp : ta cle est vide. Refais glisser le copieur sur le "
            "graphique et colle ta cle (as_...) dans le champ CleApi, "
            "onglet Parametres d entree.");
      return INIT_FAILED;
     }
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      Alerte("Trading automatique DÉSACTIVÉ : clique sur le bouton "
             "« Algo Trading » dans la barre d'outils de MetaTrader.");
      Alert("AlphaScalp : le trading automatique est DESACTIVE. Clique sur "
            "le bouton Algo Trading en haut de MetaTrader, il doit etre vert.");
      return INIT_FAILED;
     }
   if(RisqueParTrade <= 0.0 || RisqueParTrade > 5.0)
     {
      Alerte("RisqueParTrade doit être entre 0.1 et 5.0 (valeur reçue : " +
             DoubleToString(RisqueParTrade, 2) + ").");
      Alert("AlphaScalp : RisqueParTrade doit etre entre 0.1 et 5.0. "
            "Mets 1.0 pour commencer.");
      return INIT_FAILED;
     }

   // Fichiers nommés par numéro de compte : deux comptes sur le même
   // terminal ne se marchent pas dessus.
   string suffixeCompte = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   cheminCurseur = "AlphaScalp_curseur_" + suffixeCompte + ".txt";
   cheminMap     = "AlphaScalp_map_"     + suffixeCompte + ".txt";
   MapCharger();
   MapNettoyer();

   //--- Curseur : reprendre où on s'était arrêté --------------------
   if(ChargerCurseur())
      Info("Reprise au signal n°" + IntegerToString(curseur));
   else
     {
      // Premier lancement : on part du DERNIER signal connu du serveur.
      // Sinon l'EA rejouerait tout l'historique et ouvrirait des trades
      // sur des setups vieux de plusieurs jours.
      string reponse;
      int code = HttpGet(AdresseServeur + "/api/status", reponse);
      if(code == 200)
        {
         curseur = (long)JsonNombre(reponse, "latest_signal_id", 0);
         SauverCurseur();
         Info("Premier lancement — départ au signal n°" +
              IntegerToString(curseur) + " (l'historique n'est pas rejoué).");
         // /api/status répond 200 même si la clé est inactive (seul
         // /api/signals renvoie 403). On lit donc l'état ici pour prévenir
         // dès le démarrage plutôt qu'au premier signal manqué.
         if(JsonTexte(reponse, "active", "false") != "true")
           {
            enPause = true;
            Alerte("Clé encore INACTIVE côté AlphaScalp : aucune entrée ne "
                   "sera prise. L'EA reste en veille et se réveillera tout "
                   "seul dès l'activation, rien à relancer.");
           }
        }
      else if(code == 401)
        {
         // [31/07] On ne renvoie PLUS INIT_FAILED ici. L'EA se retirait du
         // graphique, obligeant a tout reinstaller a la main. Or la cause la
         // plus frequente n'est pas une faute de frappe : c'est le serveur
         // gratuit qui repart sur un disque vide et oublie les inscriptions.
         // Dans ce cas la cle est bonne, et l'acces revient des que le testeur
         // la recupere. Un EA qui reste en place se repare tout seul ; un EA
         // qui s'est retire demande une intervention.
         // Le cas d'une vraie faute de frappe n'est pas perdu pour autant :
         // l'avertissement se repete toutes les 5 minutes.
         Alerte("Cle REFUSEE au demarrage. Soit CleApi comporte une faute "
                "(elle commence par as_), soit le serveur a ete reinitialise "
                "et a oublie les inscriptions.");
         Alerte("L'EA RESTE EN PLACE et reessaiera : rien a reinstaller. Pour "
                "recuperer la meme cle, va sur " + AdresseServeur +
                "/rejoindre , rubrique 'cle perdue' (email + date de "
                "naissance), puis demande la reactivation.");
         Alert("AlphaScalp : cle refusee par le serveur. Voir le Journal des "
               "experts. L'EA reste en place et reprendra tout seul.");
         curseur = -1;  // NON ETABLI : Relever() le fixera au dernier signal
        }                //             connu. Surtout pas 0 = rejouer tout.
      else
        {
         Alerte("Impossible de joindre le serveur au démarrage "
                "(HTTP " + IntegerToString(code) + "). Nouvelle tentative "
                "au prochain cycle.");
         curseur = -1;  // NON ETABLI. C'etait 0 ici, et 0 veut dire "envoie-moi
        }                // TOUT l'historique" : le chemin le plus frequent du
                         // premier lancement rejouait des signaux perimes.
     }

   // [03/08] Le plancher n'est plus un chiffre choisi à la main (c'était 5),
   // il est DÉDUIT des délais réseau. Tant que la période peut être plus courte
   // que le temps d'attente maximal, les événements du timer s'empilent et la
   // charte cesse de répondre. Lier les deux rend cette situation impossible
   // par construction, y compris si quelqu'un modifie un délai plus tard.
   int plancher = (DELAI_SIGNAUX_MS + DELAI_ETAT_MS) / 1000 + 2;   // 10 s
   int periode  = MathMax(plancher, IntervalleSecondes);
   if(IntervalleSecondes < plancher)
      Alerte(StringFormat("Intervalle demandé (%d s) trop court : porté à %d s. "
                          "En dessous, MetaTrader peut cesser de répondre.",
                          IntervalleSecondes, periode));
   EventSetTimer(periode);
   initialisationOk = true;

   Info(StringFormat("Compte %I64d | capital %.2f %s | risque %.1f%% | "
                     "max %d positions | relève toutes les %ds",
                     AccountInfoInteger(ACCOUNT_LOGIN),
                     AccountInfoDouble(ACCOUNT_EQUITY),
                     AccountInfoString(ACCOUNT_CURRENCY),
                     RisqueParTrade, PositionsMaximum, periode));
   Info("Rappel : ce terminal doit rester ALLUMÉ pour que la copie fonctionne.");
   RapporterEtat();                 // premier rapport : version, courtier, compte
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int raison)
  {
   EventKillTimer();
   if(initialisationOk)
      Info("Arrêté (raison " + IntegerToString(raison) +
           "). Les positions ouvertes ne sont plus suivies — "
           "elles gardent leur SL et leur TP.");
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   if(!initialisationOk) return;
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return;   // bouton Algo Trading coupé
   MapNettoyer();                                   // purge des positions closes
   Relever();
   RapporterEtat();                                 // throttlé à 15 min
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Rien : tout passe par le minuteur. Un EA piloté au tick dépendrait du
   // symbole du graphique sur lequel il est posé, ce qui n'a aucun sens ici.
  }
//+------------------------------------------------------------------+
