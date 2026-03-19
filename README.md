# DGSI-LAB4
1. How does your program know when to stop calling the LLM?

Mi programa deja de llamar al modelo cuando la respuesta ya no trae ninguna petición de herramienta. Mientras el modelo sigue pidiendo acciones, el bucle continúa. En cambio, cuando devuelve una respuesta normal, sin pedir nada más, el programa entiende que esa ya es la respuesta final y ahí se para.

![Schermata iniziale](image/01_initial.png)

2. What is the role of tool_call_id in the message protocol?

Sirve para relacionar cada resultado con la llamada concreta que hizo antes el modelo. O sea, es como la forma de no mezclar una respuesta de una herramienta con otra. Gracias a eso, el sistema sabe exactamente qué resultado pertenece a qué petición.

3. Why is user confirmation important for wget but not for execute_sql?

Porque la descarga desde internet implica una acción externa y ahí tiene más sentido pedir permiso antes de ejecutarla. En cambio, la otra herramienta trabaja sobre la base de datos local de la práctica, así que estaba mucho más controlada y no tenía el mismo nivel de riesgo.

![Prompt wget e richiesta di conferma](image/03_wget.png)

4. What happens in the conversation when the user denies a wget command?

Cuando el usuario no da permiso, la descarga no se ejecuta. Ese resultado se añade igualmente a la conversación y el modelo lo ve en la siguiente ronda. Entonces responde teniendo en cuenta que no pudo hacer esa parte, en lugar de inventarse un resultado como si la descarga hubiera funcionado.

![Esempio: wget negato / errore](image/06_error.png)

5. How many iterations did the loop run for the full test prompt? Were you surprised?

En mi caso fueron cinco iteraciones. Primero hizo la descarga, luego creó la tabla, después insertó los datos, luego consultó el contenido y al final dio la respuesta final. La verdad es que no me sorprendió demasiado, porque viendo la tarea era bastante lógico que hiciera más o menos esos pasos.

![Loop delle iterazioni](image/02_loop.png)
![Step finale / risultato della fase 5](image/05_step5.png)