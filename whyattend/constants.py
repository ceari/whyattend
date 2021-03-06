"""
    Constants
    ~~~~~~~~~

    Constants and translations used in WoT replay files and the API.
"""

MAP_EN_NAME_BY_ID = {
    "01_karelia": "Karelia",
    "02_malinovka": "Malinovka",
    "04_himmelsdorf": "Himmelsdorf",
    "05_prohorovka": "Prokhorovka",
    "07_lakeville": "Lakeville",
    "06_ensk": "Ensk",
    "11_murovanka": "Murovanka",
    "13_erlenberg": "Erlenberg",
    "10_hills": "Mines",
    "15_komarin": "Komarin",
    "18_cliff": "Cliff",
    "19_monastery": "Abbey",
    "28_desert": "Sand River",
    "35_steppes": "Steppes",
    "37_caucasus": "Mountain Pass",
    "33_fjord": "Fjords",
    "34_redshire": "Redshire",
    "36_fishing_bay": "Fisherman's Bay",
    "38_mannerheim_line": "Arctic Region",
    "08_ruinberg": "Ruinberg",
    "14_siegfried_line": "Siegfried Line",
    "22_slough": "Swamp",
    "23_westfeld": "Westfield",
    "29_el_hallouf": "El Halluf",
    "31_airfield": "Airfield",
    "03_campania": "Province",
    "17_munchen": "Widepark",
    "44_north_america": "Live Oaks",
    "39_crimea": "South Coast",
    "45_north_america": "Highway",
    "42_north_america": "Port",
    "51_asia": "Dragon Ridge",
    "47_canada_a": "Serene Coast",
    "85_winter": "Belogorsk-19",
    "73_asia_korea": "Sacred Valley",
    "60_asia_miao": "Pearl River",
    "00_tank_tutorial": "Training area",
    "86_himmelsdorf_winter": "Himmelsdorf Winter",
    "87_ruinberg_on_fire": "Ruinberg on Fire",
    "63_tundra": "Tundra",
    "84_winter": "Windstorm",
    "83_kharkiv": "Kharkov"
}


WOT_TANKS = {
 u'A-20': {'tier': 4},
 u'A-32': {'tier': 4},
 u'A104_M4A3E8A': {'tier': 6},
 u'A43': {'tier': 6},
 u'A44': {'tier': 7},
 u'AMX38': {'tier': 3},
 u'AMX40': {'tier': 4},
 u'AMX50_Foch': {'tier': 9},
 u'AMX_105AM': {'tier': 5},
 u'AMX_12t': {'tier': 6},
 u'AMX_13F3AM': {'tier': 6},
 u'AMX_13_75': {'tier': 7},
 u'AMX_13_90': {'tier': 8},
 u'AMX_50Fosh_155': {'tier': 10},
 u'AMX_50_100': {'tier': 8},
 u'AMX_50_120': {'tier': 9},
 u'AMX_50_68t': {'tier': 10},
 u'AMX_AC_Mle1946': {'tier': 7},
 u'AMX_AC_Mle1948': {'tier': 8},
 u'AMX_M4_1945': {'tier': 7},
 u'AMX_Ob_Am105': {'tier': 4},
 u'ARL_44': {'tier': 6},
 u'ARL_V39': {'tier': 6},
 u'AT-1': {'tier': 2},
 u'Auf_Panther': {'tier': 7},
 u'B-1bis_captured': {'tier': 4},
 u'B1': {'tier': 4},
 u'BDR_G1B': {'tier': 5},
 u'BT-2': {'tier': 2},
 u'BT-7': {'tier': 3},
 u'BT-SV': {'tier': 3},
 u'Bat_Chatillon155': {'tier': 10},
 u'Bat_Chatillon155_55': {'tier': 9},
 u'Bat_Chatillon25t': {'tier': 10},
 u'Bison_I': {'tier': 3},
 u'Ch01_Type59': {'tier': 8},
 u'Ch02_Type62': {'tier': 7},
 u'Ch04_T34_1': {'tier': 7},
 u'Ch05_T34_2': {'tier': 8},
 u'Ch06_Renault_NC31': {'tier': 1},
 u'Ch07_Vickers_MkE_Type_BT26': {'tier': 2},
 u'Ch08_Type97_Chi_Ha': {'tier': 3},
 u'Ch09_M5': {'tier': 4},
 u'Ch10_IS2': {'tier': 7},
 u'Ch11_110': {'tier': 8},
 u'Ch12_111_1_2_3': {'tier': 9},
 u'Ch14_T34_3': {'tier': 8},
 u'Ch15_59_16': {'tier': 6},
 u'Ch16_WZ_131': {'tier': 7},
 u'Ch17_WZ131_1_WZ132': {'tier': 8},
 u'Ch18_WZ-120': {'tier': 9},
 u'Ch19_121': {'tier': 10},
 u'Ch20_Type58': {'tier': 6},
 u'Ch21_T34': {'tier': 5},
 u'Ch22_113': {'tier': 10},
 u'Ch23_112': {'tier': 8},
 u'Ch24_Type64': {'tier': 6},
 u'Chi_Ha': {'tier': 3},
 u'Chi_He': {'tier': 4},
 u'Chi_Ni': {'tier': 2},
 u'Chi_Nu': {'tier': 5},
 u'Chi_Nu_Kai': {'tier': 5},
 u'Chi_Ri': {'tier': 7},
 u'Chi_To': {'tier': 6},
 u'Churchill_LL': {'tier': 5},
 u'D1': {'tier': 2},
 u'D2': {'tier': 3},
 u'DW_II': {'tier': 4},
 u'DickerMax': {'tier': 6},
 u'E-100': {'tier': 10},
 u'E-25': {'tier': 7},
 u'E-50': {'tier': 9},
 u'E-75': {'tier': 9},
 u'E50_Ausf_M': {'tier': 10},
 u'ELC_AMX': {'tier': 5},
 u'FCM_36Pak40': {'tier': 3},
 u'FCM_50t': {'tier': 8},
 u'Ferdinand': {'tier': 8},
 u'G101_StuG_III': {'tier': 4},
 u'G103_RU_251': {'tier': 8},
 u'G20_Marder_II': {'tier': 3},
 u'GAZ-74b': {'tier': 4},
 u'GB01_Medium_Mark_I': {'tier': 1},
 u'GB03_Cruiser_Mk_I': {'tier': 2},
 u'GB04_Valentine': {'tier': 4},
 u'GB05_Vickers_Medium_Mk_II': {'tier': 2},
 u'GB06_Vickers_Medium_Mk_III': {'tier': 3},
 u'GB07_Matilda': {'tier': 4},
 u'GB08_Churchill_I': {'tier': 5},
 u'GB09_Churchill_VII': {'tier': 6},
 u'GB10_Black_Prince': {'tier': 7},
 u'GB11_Caernarvon': {'tier': 8},
 u'GB12_Conqueror': {'tier': 9},
 u'GB13_FV215b': {'tier': 10},
 u'GB20_Crusader': {'tier': 5},
 u'GB21_Cromwell': {'tier': 6},
 u'GB22_Comet': {'tier': 7},
 u'GB23_Centurion': {'tier': 8},
 u'GB24_Centurion_Mk3': {'tier': 9},
 u'GB25_Loyd_Carrier': {'tier': 2},
 u'GB26_Birch_Gun': {'tier': 4},
 u'GB27_Sexton': {'tier': 3},
 u'GB28_Bishop': {'tier': 5},
 u'GB29_Crusader_5inch': {'tier': 7},
 u'GB30_FV3805': {'tier': 9},
 u'GB31_Conqueror_Gun': {'tier': 10},
 u'GB32_Tortoise': {'tier': 9},
 u'GB39_Universal_CarrierQF2': {'tier': 2},
 u'GB40_Gun_Carrier_Churchill': {'tier': 6},
 u'GB42_Valentine_AT': {'tier': 3},
 u'GB48_FV215b_183': {'tier': 10},
 u'GB51_Excelsior': {'tier': 5},
 u'GB57_Alecto': {'tier': 4},
 u'GB58_Cruiser_Mk_III': {'tier': 2},
 u'GB59_Cruiser_Mk_IV': {'tier': 3},
 u'GB60_Covenanter': {'tier': 4},
 u'GB63_TOG_II': {'tier': 6},
 u'GB68_Matilda_Black_Prince': {'tier': 5},
 u'GB69_Cruiser_Mk_II': {'tier': 3},
 u'GB70_FV4202_105': {'tier': 10},
 u'GB71_AT_15A': {'tier': 7},
 u'GB72_AT15': {'tier': 8},
 u'GB73_AT2': {'tier': 5},
 u'GB74_AT8': {'tier': 6},
 u'GB75_AT7': {'tier': 7},
 u'GB76_Mk_VIC': {'tier': 2},
 u'GB77_FV304': {'tier': 6},
 u'GB78_Sexton_I': {'tier': 3},
 u'GB79_FV206': {'tier': 8},
 u'GW_Mk_VIe': {'tier': 2},
 u'GW_Tiger_P': {'tier': 8},
 u'G_E': {'tier': 10},
 u'G_Panther': {'tier': 7},
 u'G_Tiger': {'tier': 9},
 u'Grille': {'tier': 5},
 u'H39_captured': {'tier': 2},
 u'Ha_Go': {'tier': 2},
 u'Hetzer': {'tier': 4},
 u'Hummel': {'tier': 6},
 u'IS': {'tier': 7},
 u'IS-3': {'tier': 8},
 u'IS-4': {'tier': 10},
 u'IS-6': {'tier': 8},
 u'IS-7': {'tier': 10},
 u'IS8': {'tier': 9},
 u'ISU-152': {'tier': 8},
 u'Indien_Panzer': {'tier': 8},
 u'JagdPanther': {'tier': 7},
 u'JagdPantherII': {'tier': 8},
 u'JagdPzIV': {'tier': 6},
 u'JagdPz_E100': {'tier': 10},
 u'JagdTiger': {'tier': 9},
 u'JagdTiger_SdKfz_185': {'tier': 8},
 u'KV-13': {'tier': 7},
 u'KV-1s': {'tier': 5},
 u'KV-220': {'tier': 5},
 u'KV-220_test': {'tier': 5},
 u'KV-3': {'tier': 7},
 u'KV-5': {'tier': 8},
 u'KV1': {'tier': 5},
 u'KV2': {'tier': 6},
 u'KV4': {'tier': 8},
 u'Ke_Ho': {'tier': 4},
 u'Ke_Ni': {'tier': 3},
 u'LTP': {'tier': 3},
 u'Leopard1': {'tier': 10},
 u'Lorraine155_50': {'tier': 7},
 u'Lorraine155_51': {'tier': 8},
 u'Lorraine39_L_AM': {'tier': 3},
 u'Lorraine40t': {'tier': 9},
 u'Lowe': {'tier': 8},
 u'Ltraktor': {'tier': 1},
 u'M103': {'tier': 9},
 u'M10_Wolverine': {'tier': 5},
 u'M12': {'tier': 7},
 u'M18_Hellcat': {'tier': 6},
 u'M22_Locust': {'tier': 3},
 u'M24_Chaffee': {'tier': 5},
 u'M24_Chaffee_GT': {'tier': 1},
 u'M2_lt': {'tier': 2},
 u'M2_med': {'tier': 3},
 u'M36_Slagger': {'tier': 6},
 u'M37': {'tier': 4},
 u'M3_Grant': {'tier': 4},
 u'M3_Stuart': {'tier': 3},
 u'M3_Stuart_LL': {'tier': 3},
 u'M40M43': {'tier': 8},
 u'M41': {'tier': 5},
 u'M41_Bulldog': {'tier': 7},
 u'M46_Patton': {'tier': 9},
 u'M48A1': {'tier': 10},
 u'M4A2E4': {'tier': 5},
 u'M4A3E8_Sherman': {'tier': 6},
 u'M4_Sherman': {'tier': 5},
 u'M53_55': {'tier': 9},
 u'M5_Stuart': {'tier': 4},
 u'M6': {'tier': 6},
 u'M60': {'tier': 10},
 u'M6A2E1': {'tier': 8},
 u'M7_Priest': {'tier': 3},
 u'M7_med': {'tier': 5},
 u'M8A1': {'tier': 4},
 u'MS-1': {'tier': 1},
 u'MT25': {'tier': 6},
 u'Marder_III': {'tier': 4},
 u'Matilda_II_LL': {'tier': 5},
 u'Maus': {'tier': 10},
 u'NC27': {'tier': 1},
 u'Nashorn': {'tier': 6},
 u'Object263': {'tier': 10},
 u'Object268': {'tier': 10},
 u'Object416': {'tier': 8},
 u'Object_140': {'tier': 10},
 u'Object_212': {'tier': 9},
 u'Object_261': {'tier': 10},
 u'Object_430': {'tier': 10},
 u'Object_704': {'tier': 9},
 u'Object_907': {'tier': 10},
 u'Panther_II': {'tier': 8},
 u'Panther_M10': {'tier': 7},
 u'PanzerJager_I': {'tier': 2},
 u'Pershing': {'tier': 8},
 u'Pro_Ag_A': {'tier': 9},
 u'Pz35t': {'tier': 2},
 u'Pz38_NA': {'tier': 4},
 u'Pz38t': {'tier': 3},
 u'PzI': {'tier': 2},
 u'PzII': {'tier': 2},
 u'PzIII_A': {'tier': 3},
 u'PzIII_AusfJ': {'tier': 4},
 u'PzIII_IV': {'tier': 5},
 u'PzII_J': {'tier': 3},
 u'PzII_Luchs': {'tier': 4},
 u'PzIV_Hydro': {'tier': 5},
 u'PzIV_schmalturm': {'tier': 6},
 u'PzI_ausf_C': {'tier': 3},
 u'PzV': {'tier': 7},
 u'PzVI': {'tier': 7},
 u'PzVIB_Tiger_II': {'tier': 8},
 u'PzVI_Tiger_P': {'tier': 7},
 u'PzV_PzIV': {'tier': 6},
 u'PzV_PzIV_ausf_Alfa': {'tier': 6},
 u'Pz_II_AusfG': {'tier': 3},
 u'Pz_IV_AusfA': {'tier': 3},
 u'Pz_IV_AusfD': {'tier': 4},
 u'Pz_IV_AusfH': {'tier': 5},
 u'Pz_Sfl_IVb': {'tier': 4},
 u'Pz_Sfl_IVc': {'tier': 5},
 u'R104_Object_430_II': {'tier': 9},
 u'R106_KV85': {'tier': 6},
 u'R107_LTB': {'tier': 7},
 u'R109_T54S': {'tier': 8},
 u'Ram-II': {'tier': 5},
 u'RenaultBS': {'tier': 2},
 u'RenaultFT': {'tier': 1},
 u'RenaultFT_AC': {'tier': 2},
 u'RenaultUE57': {'tier': 3},
 u'RhB_Waffentrager': {'tier': 8},
 u'S-51': {'tier': 7},
 u'S35_captured': {'tier': 3},
 u'STA_1': {'tier': 8},
 u'ST_B1': {'tier': 10},
 u'ST_I': {'tier': 9},
 u'SU-100': {'tier': 6},
 u'SU-101': {'tier': 8},
 u'SU-14': {'tier': 8},
 u'SU-152': {'tier': 7},
 u'SU-18': {'tier': 2},
 u'SU-26': {'tier': 3},
 u'SU-5': {'tier': 4},
 u'SU-76': {'tier': 3},
 u'SU-8': {'tier': 6},
 u'SU-85': {'tier': 5},
 u'SU100M1': {'tier': 7},
 u'SU100Y': {'tier': 6},
 u'SU122A': {'tier': 5},
 u'SU122_44': {'tier': 7},
 u'SU122_54': {'tier': 9},
 u'SU14_1': {'tier': 7},
 u'SU_85I': {'tier': 5},
 u'S_35CA': {'tier': 5},
 u'Sherman_Jumbo': {'tier': 6},
 u'Somua_Sau_40': {'tier': 4},
 u'StuG_40_AusfG': {'tier': 5},
 u'Sturer_Emil': {'tier': 7},
 u'Sturmpanzer_II': {'tier': 4},
 u'T-127': {'tier': 3},
 u'T-15': {'tier': 3},
 u'T-25': {'tier': 5},
 u'T-26': {'tier': 2},
 u'T-28': {'tier': 4},
 u'T-34': {'tier': 5},
 u'T-34-85': {'tier': 6},
 u'T-43': {'tier': 7},
 u'T-44': {'tier': 8},
 u'T-46': {'tier': 3},
 u'T-50': {'tier': 4},
 u'T-54': {'tier': 9},
 u'T-60': {'tier': 2},
 u'T-70': {'tier': 3},
 u'T110': {'tier': 10},
 u'T110E3': {'tier': 10},
 u'T110E4': {'tier': 10},
 u'T14': {'tier': 5},
 u'T150': {'tier': 6},
 u'T18': {'tier': 2},
 u'T1_Cunningham': {'tier': 1},
 u'T1_E6': {'tier': 2},
 u'T1_hvy': {'tier': 5},
 u'T20': {'tier': 7},
 u'T21': {'tier': 6},
 u'T23E3': {'tier': 7},
 u'T25_2': {'tier': 7},
 u'T25_AT': {'tier': 7},
 u'T26_E4_SuperPershing': {'tier': 8},
 u'T28': {'tier': 8},
 u'T28_Prototype': {'tier': 8},
 u'T29': {'tier': 7},
 u'T2_lt': {'tier': 2},
 u'T2_med': {'tier': 2},
 u'T30': {'tier': 9},
 u'T32': {'tier': 8},
 u'T34_hvy': {'tier': 8},
 u'T37': {'tier': 6},
 u'T40': {'tier': 4},
 u'T49': {'tier': 8},
 u'T54E1': {'tier': 9},
 u'T57': {'tier': 2},
 u'T57_58': {'tier': 10},
 u'T62A': {'tier': 10},
 u'T67': {'tier': 5},
 u'T69': {'tier': 8},
 u'T71': {'tier': 7},
 u'T7_Combat_Car': {'tier': 2},
 u'T80': {'tier': 4},
 u'T82': {'tier': 3},
 u'T92': {'tier': 10},
 u'T95': {'tier': 9},
 u'Te_Ke': {'tier': 2},
 u'Tetrarch_LL': {'tier': 2},
 u'Type_61': {'tier': 9},
 u'VK1602': {'tier': 5},
 u'VK2001DB': {'tier': 4},
 u'VK2801': {'tier': 6},
 u'VK3001H': {'tier': 5},
 u'VK3001P': {'tier': 6},
 u'VK3002DB': {'tier': 7},
 u'VK3002DB_V1': {'tier': 6},
 u'VK3002M': {'tier': 6},
 u'VK3601H': {'tier': 6},
 u'VK4502A': {'tier': 8},
 u'VK4502P': {'tier': 9},
 u'VK7201': {'tier': 10},
 u'Valentine_LL': {'tier': 4},
 u'Waffentrager_E100': {'tier': 10},
 u'Waffentrager_IV': {'tier': 9},
 u'Wespe': {'tier': 3},
 u'_105_leFH18B2': {'tier': 5},
 u'_Hotchkiss_H35': {'tier': 2},
 u'_M44': {'tier': 6}
}
