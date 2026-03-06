<?php


/* 
 * Copyright (c) 2014, Carlos López Martínez <webtendsolutions@gmail.com>
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

//include('../libs/simple_html_dom/simple_html_dom.php');
require_once ("../include/autoload.php");

//http://www.futbolfantasy.com/laliga/jugadores/jorge-f-burgui/2019#MED
$jornada_actual=1;
$temporada='2018-2019';
extract($_REQUEST);
$db = new Bbdd();
//SELECT id_user,nombre,SUM(ptos_jor) AS total_jornada FROM jornadas j LEFT JOIN usuarios u ON j.id_user=u.id where jornada=5 and alineado=1 group by id_user;
$copa=array();
$copa=$db->select("SELECT `id_user`,`nombre`,`jornada`,SUM(`gol`)+SUM(`gol_p`) as `goles`,SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`)as `goles_c`,(CASE WHEN (SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`)) > (SUM(`gol`)+SUM(`gol_p`)) THEN 0 WHEN (SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`)) < (SUM(`gol`)+SUM(`gol_p`)) THEN 3 ELSE 1 END) AS ptos, SUM(`gol`)+SUM(`gol_p`)-SUM(IF(`pos` = 'POR', `gol_c`, 0)) - SUM(`gol_pp`) as `avg` FROM `jornadas_temp` j LEFT JOIN `usuarios_temp` u ON j.`id_user`=u.`id` and  j.`temporada`=u.`temporada` where j.`jornada`=".$jornada_actual." and j.`temporada`='".$temporada."' and `alineado`=1 group by `id_user` order by `ptos` desc,`avg` desc");
// $query1=array();
// $query1=$db->select("SELECT id_user,nombre,SUM(`gol_c`) as `goles_c` FROM `jornadas` j LEFT JOIN `usuarios` u ON j.`id_user`=u.`id` where `jornada`=".$jornada_actual." and `alineado`=1 and `pos`='POR' group by `id_user`");
// $query2=array();
// $query2=$db->select("SELECT id_user,nombre,jornada,SUM(`gol`)+SUM(`gol_p`) as `goles`,SUM(`gol_pp`) as `goles_pp` FROM `jornadas` j LEFT JOIN `usuarios` u ON j.`id_user`=u.`id` where `jornada`=".$jornada_actual." and `alineado`=1 group by `id_user`;");
// $object = new stdClass();

// foreach ($query1 as $clave => $valor) {
//     $object->id_user = $valor['id_user'];
//     $object->nombre = $valor['nombre'];
//     $object->goles_c = $valor['goles_c'];
//     foreach ($query2 as $key => $value) {
//         echo((int)$valor['id_user']." -".(int)$value['id_user']);
//         if ((int)$valor['id_user']==(int)$value['id_user']){
//             $object->goles = $value['goles'];
//             $object->goles_pp = $value['goles_pp'];
//             $dif=(int)$value['goles']-((int)$value['goles_pp']+(int)$valor['goles_c']);
//             $ptos=0;
//             if ($dif>0) $ptos=3;
//             else if($dif==0) $ptos=1;
//             else $ptos=0;
//             $object->ptos=$ptos;
//             $object->avg=$dif;
//         }
//     }
//     $copa[(int)$valor['id_user']]=(array)$object;
// }    


$json=json_encode($copa);
header('Content-Type: application/json');
echo($json);
$db->close();

?>