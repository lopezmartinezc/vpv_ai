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
$j=1;
for ($i = 1; $i <= (int)$jornada_actual; $i++) {
    $query=array();
    $query=$db->select("SELECT `id_user`,`nombre`,`jornada`,SUM(`gol`)+SUM(`gol_p`) as `goles`,SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`)as `goles_c`,(CASE WHEN (SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`)) > (SUM(`gol`)+SUM(`gol_p`)) THEN 0 WHEN (SUM(IF(`pos` = 'POR', `gol_c`, 0)) + SUM(`gol_pp`))< (SUM(`gol`)+SUM(`gol_p`)) THEN 3 ELSE 1 END) AS ptos, SUM(`gol`)+SUM(`gol_p`)-SUM(IF(`pos` = 'POR', `gol_c`, 0)) - SUM(`gol_pp`) as `avg` FROM `jornadas_temp` j LEFT JOIN `usuarios_temp` u ON j.`id_user`=u.`id` and  j.`temporada`=u.`temporada` where `jornada`=".$i." and j.`temporada`='".$temporada."' and `alineado`=1 group by `id_user` order by `ptos` desc,`avg` desc");
$json=json_encode($usuarios);
    if (count($query)>0){
        foreach ($query as $clave => $valor) {
            if($j==1){
                $object = new stdClass();
                $object->id_user = $valor['id_user'];
                $object->nombre = $valor['nombre'];
                $object->ptos = $valor['ptos'];
                $object->avg = $valor['avg'];
                $copa[(int)$valor['id_user']]=(array)$object;
                unset($object);
            }
            else{
                $copa[(int)$valor['id_user']]['ptos']=$copa[(int)$valor['id_user']]['ptos']+(int)$valor['ptos'];
                $copa[(int)$valor['id_user']]['avg']=$copa[(int)$valor['id_user']]['avg']+(int)$valor['avg'];
            }
        }
        $j=$j+1;
    }
}
$res=array();
foreach ($copa as $clave => $valor) {
    $res[]=$valor;
}

foreach ($res as $key => $row) {
    $ptos[$key]  = $row['ptos'];
    $avg[$key] = $row['avg'];
}
array_multisort($ptos, SORT_DESC, $avg, SORT_DESC, $res);
$json=json_encode($res);
header('Content-Type: application/json');
echo($json);
$db->close();

?>