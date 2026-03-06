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
$res=array();
extract($_REQUEST);
$db = new Bbdd();
//SELECT id_user,nombre,SUM(ptos_jor) AS total_jornada FROM jornadas j LEFT JOIN usuarios u ON j.id_user=u.id where jornada=5 and alineado=1 group by id_user;
$pago=array();
$query2=array();
$query2=$db->select("SELECT * FROM `usuarios_temp` where `temporada`='".$temporada."'");
$total_participants=count($query2);
$query=array();
$query=$db->select("SELECT `id_user`,`nombre`,SUM(`ptos_jor`) AS `total_jornada` FROM `jornadas_temp` j LEFT JOIN `usuarios_temp` u ON j.`id_user`=u.`id` and  j.`temporada`=u.`temporada` where `jornada`=".$jornada_actual." and j.`temporada`='".$temporada."' and `alineado`=1 group by `id_user` order by total_jornada desc");

if (count($query)>0){
    $i=1;
    foreach ($query as $clave => $valor) {
        
        $object = new stdClass();
        $object->id_user = $valor['id_user'];
        $object->nombre = $valor['nombre'];
        $object->ptos = (int)$valor['total_jornada'];
        /*if (($i>0)&&($i<7))   $object->pago = 0 ;
        else if ($i==7) $object->pago = 0.5 ;
        else if (($i>7)&&($i<11)) $object->pago = 1 ;
        else if (($i>10)&&($i<13)) $object->pago = 1.5 ;
        else if ($i==13) $object->pago = 2 ;*/
        if ($i <= 5) {
            $object->pago = 0;
        } else if ($i == 6) {
            $object->pago = 0.5;
        } else if ($i == $total_participants) {
            $object->pago = 2;
        } else if ($i == $total_participants - 1 || $i == $total_participants - 2) {
            $object->pago = 1.5;
        } else {
            $object->pago = 1;
        }
        $pago[$i]=(array)$object;
        unset($object);
        $i=$i+1;
    }
    $comp=0;
    $cash=0;
    $i=13;
    foreach (array_reverse($pago) as  $clave => $valor) {
        //echo('$i:'.$i.' - $comp:'.$comp.' - $cash:'.$cash);
        if ($i==13){ $comp=$valor['ptos'];$cash=$valor['pago'];}
        else{
            if ($valor['ptos']>$comp) { $comp=$valor['ptos'];$cash=$valor['pago'];} 
            else   { $comp=$valor['ptos'];$pago[$i]['pago']=$cash;} 
        }
        //echo('$i:'.$i.' - $comp:'.$comp.' - $cash:'.$cash);
        $i=$i-1;
    }

    $res=array();
    foreach ($pago as $clave => $valor) {
        $res[]=$valor;
    }

}


$json=json_encode($res);
header('Content-Type: application/json');
echo($json);
$db->close();

?>