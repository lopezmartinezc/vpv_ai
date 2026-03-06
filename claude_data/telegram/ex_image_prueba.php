<?php
include('telegram_api.php');
$alineacion=[];
$jug = [
    "pos" => "POR", 
    "nom_url" => "aaron-escandell",
    "nom" => "Aaron Escandell"
  ];
array_push($alineacion,$jug);
$jug2 = [
    "pos" => "DEF", 
    "nom_url" => "abdel-abqar",
    "nom" => "Abdel Abqar"
  ];
array_push($alineacion,$jug2);
$jug2 = [
    "pos" => "DEF", 
    "nom_url" => "abdel-abqar",
    "nom" => "Abdel Abqar"
  ];
array_push($alineacion,$jug2);
$jug2 = [
    "pos" => "DEF", 
    "nom_url" => "abdel-abqar",
    "nom" => "Abdel Abqar"
  ];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "DEF", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "MED", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "MED", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "MED", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "DEL", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "DEL", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$jug2 = [
  "pos" => "DEL", 
  "nom_url" => "abdel-abqar",
  "nom" => "Abdel Abqar"
];
array_push($alineacion,$jug2);
$posiciones=["1-4-3-3"];
$pos_map = [
  "1-3-4-3" => ["POR" =>[[780,1325]],"DEF" =>[[173,1000],[779,1000],[1385,1000]],"MED" =>[[97,550],[552,630],[1007,630],[1462,550]],"DEL" =>[[173,180],[779,180],[1385,180]] ],
  "1-3-5-2" => ["POR" =>[[780,1325]],"DEF" =>[[173,1000],[779,1000],[1385,1000]],"MED" =>[[52,500],[416,570],[780,650],[1144,570],[1508,500]],"DEL" =>[[325,180],[1235,180]] ],
  "1-4-3-3" => ["POR" =>[[780,1325]],"DEF" =>[[97,1000],[552,1000],[1007,1000],[1462,1000]],"MED" =>[[173,550],[779,550],[1385,550]],"DEL" =>[[173,180],[779,180],[1385,180]] ],
  "1-4-4-2" => ["POR" =>[[780,1325]],"DEF" =>[[97,1000],[552,1000],[1007,1000],[1462,1000]],"MED" =>[[97,550],[552,630],[1007,630],[1462,550]],"DEL" =>[[325,180],[1235,180]] ],
  "1-4-5-1" => ["POR" =>[[780,1325]],"DEF" =>[[97,1000],[552,1000],[1007,1000],[1462,1000]],"MED" =>[[52,500],[416,570],[780,650],[1144,570],[1508,500]],"DEL" =>[[780,180]] ],
  "1-5-3-2" => ["POR" =>[[780,1325]],"DEF" =>[[52,870],[416,920],[780,1000],[1144,920],[1508,870]],"MED" =>[[173,520],[779,520],[1385,520],[1462,520]],"DEL" =>[[325,180],[1235,180]] ],
  "1-5-4-1" => ["POR" =>[[780,1325]],"DEF" =>[[52,870],[416,920],[780,1000],[1144,920],[1508,870]],"MED" =>[[97,520],[552,520],[1007,520],[1462,520]],"DEL" =>[[780,180]] ]
];



$img=__DIR__.'/images/field5.png';
$newimg=__DIR__.'/images/field_mod.png';
$dest=__DIR__.'/images/cache/field_mod_2.png';
$font = __DIR__ . "/fuentes/Roboto-Medium.ttf";
$font_bold = __DIR__ . "/fuentes/Roboto-Bold.ttf";
copy($img, $newimg);

$imagen = imagecreatefrompng($newimg);
$negro = imagecolorallocate($imagen, 0, 0, 0);
$blanco = imagecolorallocate($imagen, 255, 255, 255);
$tamanio = 60;
$angulo = 0;
$texto = "CARLOS - Jornada 10";
$box=imageftbbox($tamanio,$angulo,$font,$texto);
$ancho=$box[4]-$box[6];
$alto=$box[1]-$box[7];
$x=intval((1820-$ancho)/2);
$y=intval((84-$alto)/2)+$alto;
imagettftext($imagen, $tamanio, $angulo, $x, $y, $negro, $font, $texto);
$posx=0;
$posy=0;
$count_por=$count_def=$count_med=$count_del=0;
foreach ($alineacion as $valor){
    echo $valor["pos"].' - '.$valor["nom_url"];
    if ($valor["pos"]=='POR') {
        $posx=$pos_map[$posiciones[0]]["POR"][$count_por][0];
        $posy=$pos_map[$posiciones[0]]["POR"][$count_por][1];
        $count_por=$count_por+1;
    }
    elseif ($valor["pos"]=='DEF') {
        $posx=$pos_map[$posiciones[0]]["DEF"][$count_def][0];
        $posy=$pos_map[$posiciones[0]]["DEF"][$count_def][1];
        $count_def=$count_def+1;
    }
    elseif ($valor["pos"]=='MED') {
        $posx=$pos_map[$posiciones[0]]["MED"][$count_med][0];
        $posy=$pos_map[$posiciones[0]]["MED"][$count_med][1];
        $count_med=$count_med+1;
    }
    elseif ($valor["pos"]=='DEL') {
      $posx=$pos_map[$posiciones[0]]["DEL"][$count_del][0];
      $posy=$pos_map[$posiciones[0]]["DEL"][$count_del][1];
      $count_del=$count_del+1;
    }

    $icon=__DIR__.'/images/jugadores/'.$valor["nom_url"].'.png';
    $src = imagecreatefrompng($icon);
    $tamanio = 46;
    $icon_size=260;
    $thumb = imagescale($src, $icon_size, $icon_size, IMG_BICUBIC);
    imagecopy($imagen, $thumb, $posx, $posy, 0, 0, $icon_size, $icon_size);
    $box=imageftbbox($tamanio,$angulo,$font_bold,$valor["nom"]);
    $ancho=$box[4]-$box[6];
    $alto=$box[1]-$box[7];
    $x=($posx+intval($icon_size/2))-intval($ancho/2);
    $y=$posy+$icon_size+$alto;
    imagettftext($imagen,$tamanio, $angulo, $x, $y, $negro, $font_bold, trim($valor["nom"]));
}
imagepng($imagen,$dest);
imagedestroy($imagen);
sendPhoto($dest);

