# Week 04 - Function Calling con bucle (wget + SQLite)

## 0. Contexto y objetivo

En esta practica, como grupo, implementamos un programa en Python donde el LLM puede usar 2 herramientas:

- `wget`: descarga contenido de una URL (con confirmación humana)
- `execute_sql`: ejecuta SQL sobre SQLite

La parte clave era hacerlo en bucle de rondas, no en una sola llamada.


---

## 1. Step 0 - Research previo

### 1.1 SQLite y `sqlite3`

Comprobamos en CLI:

- crear tabla
- insertar filas
- seleccionar datos
- ver .schema y .tables

Lo importante que vimos: SQLite no es un servidor, es un archivo .db. Para esta practica viene bien por simplicidad, aunque para escenarios grandes o mucha concurrencia tendria mas sentido una BD de servidor.

Evidencia:

- `evidence/step0_research.txt`

### 1.2 `subprocess.run()`

Probamos un comando con sleep para verificar comportamiento.  
Conclusion: subprocess.run() bloquea hasta que acaba (sincronizo).

Tambien repasamos:

- capture_output=True para capturar salida
- text=True para trabajar con strings
- timeout para evitar bloqueos largos

Evidencia:

- `evidence/step0_research.txt`

### 1.3 `wget`

Probamos:

- URL valida
- URL no existente

Con URL invalida salida codigo de error (exit code 4), y eso nos sirvirá luego para Step 5.

Evidencia:

- `evidence/step0_research.txt`

---

## 2. Step 1 - Setup y una tool call

Estructura que dejamos en el proyecto:

- `tool_loop_agent.py`
- `.env.example`
- `.gitignore`
- `pyproject.toml`

Schema de `execute_sql` (fragmento):

```python
{
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": "Run SQL against local SQLite database.db.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"],
        },
    },
}
```

Prueba del paso:

- prompt para crear tabla test
- el modelo pidió execute_sql
- se ejecuta correctamente

Evidencia:

- `evidence/step1_single_tool_call.txt`

---

## 3. Step 2 - Loop con varias tool calls

Implementamos el patrón de loop: llamar al modelo, ejecutar tools, devolver resultados, repetir.

Fragmento del bucle:

```python
if not message.tool_calls:
    final_text = message.content or ""
    return final_text

messages.append({"role": "assistant", "tool_calls": [...]})
...
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,
    "name": tool_name,
    "content": tool_result,
})
```

Prueba del paso:

- prompt: crear tabla cities e insertar 3 ciudades
- se observaron llamadas secuenciales de execute_sql

Evidencia:

- `evidence/step2_loop_sequence.txt`

Como sabe el programa cuándo parar: cuando la respuesta ya no trae tool_calls.

---

## 4. Step 3 - Tool `wget` con confirmación humana

Schema de wget (fragmento):

```python
{
    "type": "function",
    "function": {
        "name": "wget",
        "description": "Fetch content from a URL using system wget. This tool requires explicit user approval before running.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "flags": {"type": "string"},
            },
            "required": ["url"],
        },
    },
}
```

Logica de confirmacion (fragmento):

```python
print(f"[confirm] LLM wants to run: {command_text}")
answer = input("Allow command? (y/n): ").strip().lower()
if answer != "y":
    return json_result(False, error="USER DENIED: command was not executed.")
```

Probamos los 2 escenarios pedidos:

1. aprobación de comando
2. denegación de comando

Evidencia:

- `evidence/step3_wget_approve.txt`
- `evidence/step3_wget_deny.txt`

---

## 5. Step 4 - Test completo (fetch + store + query)

Prompt usado:

`Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, and city of every user in a SQLite table called users. Show me the final contents of the table.`

Flujo observado en nuestra ejecución principal:

1. `wget`
2. `execute_sql` para `CREATE TABLE`
3. `execute_sql` para `INSERT`
4. `execute_sql` para `SELECT`
5. respuesta final del asistente

Iteraciones del loop en este test: **5**

Evidencias:

- salida principal: `evidence/step4_full_test.txt`
- verificación independiente: `evidence/step4_sqlite_verify.txt`

La verificación con sqlite3 devolvió las 10 filas esperadas.

---

## 6. Step 5 - Salida legible y manejo de errores

Mejoramos logs para mostrar:

- nombre del tool
- argumentos
- preview del resultado

Y protegimos ejecución con try/except para evitar ca­da del programa.

Errores probados:

1. URL invalida
2. SQL invalido (tabla inexistente)
3. denegación de wget

Evidencias:

- `evidence/step5_bad_url.txt`
- `evidence/step5_invalid_sql.txt`
- `evidence/step3_wget_deny.txt`

En todos los casos el programa siguió funcionando y devolvió error controlado al modelo.

---

## 7. Preguntas obligatorias

### 1) How does your program know when to stop calling the LLM?

Para cuando message.tool_calls está vacío. En ese punto se toma message.content como respuesta final.

### 2) What is the role of `tool_call_id` in the message protocol?

Permite enlazar cada mensaje role=tool con la llamada exacta que pidió el asistente. Sin eso, la conversación de tools se descoordina.

### 3) Why is user confirmation important for the `wget` tool but not for `execute_sql`?

`wget` toca red y recursos externos, por eso requiere validacion humana.  
`execute_sql` en este ejercicio está limitado a una BD local controlada.

### 4) What happens in the conversation when the user denies a wget command?

Se devuelve un resultado de tool tipo `USER DENIED...`, se añade al historial, y el modelo responde adaptandose a esa denegación.

### 5) How many iterations did the loop run for the full test prompt? Were you surprised?

En nuestra ejecución principal fueron 5 iteraciones. No nos sorprendió, era el número esperado para ese flujo.

---

## 8. Extra challenge (opcional) - Â¿Importa el modelo?

Probamos tambien `qwen2.5-vl-72b-instruct` con el mismo prompt.
Observamos mas iteraciones y mas errores de formato en argumentos de tool.

Evidencia:

- `evidence/extra_model_compare_qwen2_5_vl_72b.txt`

Conclusión: sí­ importa, bastante, para function calling robusto.

---

## 9. Seguridad de API key

Verificado en el proyecto:

- `.env` no se sube
- `.env.example` incluido
- `.gitignore` contiene:
  - `.env`
  - `database.db`
  - `__pycache__/`
  - `.venv/`

---

---

## 11. Anexo A - Salida completa Step 4 (raw)

```text
Week-04 Tool Loop Agent
Model: qwen3.5-122b-a10b
Endpoint: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
Database: /tmp/week04/database.db
Confirm policy: always
Prompt: Fetch https://jsonplaceholder.typicode.com/users and store the id, name, email, and city of every user in a SQLite table called users. Show me the final contents of the table.

=== Iteration 1 ===
[assistant] Requested 1 tool call(s)
[tool-call] id=call_939f4e38614b401ba2a4f6c3 name=wget
[tool-args] {"url": "https://jsonplaceholder.typicode.com/users"}
[confirm] LLM wants to run: wget -q -O - https://jsonplaceholder.typicode.com/users
[confirm] Auto-approval policy active: yes
[tool-result-preview] {"ok": true, "data": {"command": "wget -q -O - https://jsonplaceholder.typicode.com/users", "returncode": 0, "stdout": "[\n {\n \"id\": 1,\n \"name\": \"Leanne Graham\",\n \"username\": \"Bret\",\n \"email\": \"Sincere@april.biz\",\n \"address\": {\n \"street\": \"Kulas Light\",\n \"suite\": \"Apt. 556\",\n \"city\": \"Gwenborough\",\n \"zipcode\": \"92998-3874\",\n \"geo\": {\n \"lat\": \"-37.3159\",\n \"lng\": \"81.1496\"\n }\n },\n \"phone\": \"1-770-736-8031 x56442\",\n \"website\": \"hildegard.org\",\n \"company\": {\n \"name\": \"Romaguera-Crona\",\n \"catchPhrase\": \"Multi-layered client-server neural-net\",\n \"bs\": \"harness real-time e-markets\"\n }\n },\n {\n \"id\": 2,\n \"name\": \"Ervin Howell\",\n \"username\": \"Antonette\",\n \"email\": \"Shanna@melissa.tv\",\n \"address\": {\n \"street\": \"Victor Plains\",\n \"suite\": \"Suite 879\",\n \"city\": \"Wisokyburgh\",\n \"zipcode\": \"90566-7771\",\n \"geo\": {\n \"lat\": \"-43.9509\",\n \"lng\": \"-34.4618\"\n }\n },\n \"phone\": \"010-692-6593 x09125\",\n \"website\": \"anastasia.net\",\n \"company\": {\n \"name\": \"Deckow-Crist\",\n \"catchPhrase\": \"Proactive didactic contingency\",\n \"bs\": \"synergize scalable supply-chains\"\n }\n },\n {\n \"id\": 3,\n \"name\": \"Clementine Bauch\",\n \"username\": \"Samantha\",\n \"email\": \"Nathan@yesenia.net\",\n \"address\": {\n \"street\": \"Douglas Extension\",\n \"suite\": \"Suite 847\",\n \"city\": \"McKenziehaven\",\n \"zipcode\": \"59590-4157\",\n \"geo\": {\n \"lat\": \"-68.6102\",\n \"lng\": \"-47.0653\"\n }\n },\n \"phone\": \"1-463-123-4447\",\n \"website\": \"ramiro.info\",\n \"company\": {\n \"name\": \"Romaguera-Jacobson\",\n \"catchPhrase\": \"Face to face bifurcated interface\",\n \"bs\": \"e-enable strategic applications\"\n }\n },\n {\n \"id\": 4,\n \"name\": \"Patricia Lebsack\",\n \"username\": \"Karianne\",\n \"email\": \"Julianne.OConner@kory.org\",\n \"address\": {\n \"street\": \"Hoeger Mall\",\n \"suite\": \"Apt. 692\",\n \"city\": \"South Elvis\",\n \"zipcode\": \"53919-4257\",\n \"geo\": {\n \"lat\": \"29.4572\",\n \"lng\": \"-164.2990\"\n }\n },\n \"phone\": \"493-170-9623 x156\",\n \"website\": \"kale.biz\",\n \"company\": {\n \"name\": \"Robel-Corkery\",\n \"catchPhrase\": \"Multi-tiered zero tolerance productivity\",\n \"bs\": \"transition cutting-edge web services\"\n }\n },\n {\n \"id\": 5,\n \"name\": \"Chelsey Dietrich\",\n \"username\": \"Kamren\",\n \"email\": \"Lucio_Hettinger@annie.ca\",\n \"address\": {\n \"street\": \"Skiles Walks\",\n \"suite\": \"Suite 351\",\n \"city\": \"Roscoeview\",\n \"zipcode\": \"33263\",\n \"geo\": {\n \"lat\": \"-31.8129\",\n \"lng\": \"62.5342\"\n }\n },\n \"phone\": \"(254)954-1289\",\n \"website\": \"demarco.info\",\n \"company\": {\n \"name\": \"Keebler LLC\",\n \"catchPhrase\": \"User-centric fault-tolerant solution\",\n \"bs\": \"revolutionize end-to-end systems\"\n }\n },\n {\n \"id\": 6,\n \"name\": \"Mrs. Dennis Schulist\",\n \"username\": \"Leopoldo_Corkery\",\n \"email\": \"Karley_Dach@jasper.info\",\n \"address\": {\n \"street\": \"Norberto Crossing\",\n \"suite\": \"Apt. 950\",\n \"city\": \"South Christy\",\n \"zipcode\": \"23505-1337\",\n \"geo\": {\n \"lat\": \"-71.4197\",\n \"lng\": \"71.7478\"\n }\n },\n \"phone\": \"1-477-935-8478 x6430\",\n \"website\": \"ola.org\",\n \"company\": {\n \"name\": \"Considine-Lockman\",\n \"catchPhrase\": \"Synchronised bottom-line interface\",\n \"bs\": \"e-enable innovative applications\"\n }\n },\n {\n \"id\": 7,\n \"name\": \"Kurtis Weissnat\",\n \"username\": \"Elwyn.Skiles\",\n \"email\": \"Telly.Hoeger@billy.biz\",\n \"address\": {\n \"street\": \"Rex Trail\",\n \"suite\": \"Suite 280\",\n \"city\": \"Howemouth\",\n \"zipcode\": \"58804-1099\",\n \"geo\": {\n \"lat\": \"24.8918\",\n \"lng\": \"21.8984\"\n }\n },\n \"phone\": \"210.067.6132\",\n \"website\": \"elvis.io\",\n \"company\": {\n \"name\": \"Johns Group\",\n \"catchPhrase\": \"Configurable multimedia task-force\",\n \"bs\": \"generate enterprise e-tailers\"\n }\n },\n {\n \"id\": 8,\n \"name\": \"Nicholas Runolfsdottir V\",\n \"username\": \"Maxime_Nienow\",\n \"email\": \"Sherwood@rosamond.me\",\n \"address\": {\n \"street\": \"Ellsworth Summit\",\n \"suite\": \"Suite 729\",\n \"city\": \"Aliyaview\",\n \"zipcode\": \"45169\",\n \"geo\": {\n \"lat\": \"-14.3990\",\n \"lng\": \"-120.7677\"\n }\n },\n \"phone\": \"586.493.6943 x140\",\n \"website\": \"jacynthe.com\",\n \"company\": {\n \"name\": \"Abernathy Group\",\n \"catchPhrase\": \"Implemented secondary concept\",\n \"bs\": \"e-enable extensible e-tailers\"\n }\n },\n {\n \"id\": 9,\n \"name\": \"Glenna Reichert\",\n \"username\": \"Delphine\",\n \"email\": \"Chaim_McDermott@dana.io\",\n \"address\": {\n \"street\": \"Dayna Park\",\n \"suite\": \"Suite 449\",\n \"city\": \"Bartholomebury\",\n \"zipcode\": \"76495-3109\",\n \"geo\": {\n \"lat\": \"24.6463\",\n \"lng\": \"-168.8889\"\n }\n },\n \"phone\": \"(775)976-6794 x41206\",\n \"website\": \"conrad.com\",\n \"company\": {\n \"name\": \"Yost and Sons\",\n \"catchPhrase\": \"Switchable contextually-based project\",\n \"bs\": \"aggregate real-time technologies\"\n }\n },\n {\n \"id\": 10,\n \"name\": \"Clementina DuBuque\",\n \"username\": \"Moriah.Stanton\",\n \"email\": \"Rey.Padberg@karina.biz\",\n \"address\": {\n \"street\": \"Kattie Turnpike\",\n \"suite\": \"Suite 198\",\n \"city\": \"Lebsackbury\",\n \"zipcode\": \"31428-2261\",\n \"geo\": {\n \"lat\": \"-38.2386\",\n \"lng\": \"57.2232\"\n }\n },\n \"phone\": \"024-648-3804\",\n \"website\": \"ambrose.net\",\n \"company\": {\n \"name\": \"Hoeger LLC\",\n \"catchPhrase\": \"Centralized empowering task-force\",\n \"bs\": \"target end-to-end models\"\n }\n }\n]"}, "error": null}

=== Iteration 2 ===
[assistant] Requested 1 tool call(s)
[tool-call] id=call_be177700108a4924877055b4 name=execute_sql
[tool-args] {"query": "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, email TEXT, city TEXT)"}
[tool-result-preview] {"ok": true, "data": {"rowcount": -1, "lastrowid": 0}, "error": null}

=== Iteration 3 ===
[assistant] Requested 1 tool call(s)
[tool-call] id=call_2e3c409974a744bf88ce4616 name=execute_sql
[tool-args] {"query": "INSERT INTO users (id, name, email, city) VALUES (1, 'Leanne Graham', 'Sincere@april.biz', 'Gwenborough'), (2, 'Ervin Howell', 'Shanna@melissa.tv', 'Wisokyburgh'), (3, 'Clementine Bauch', 'Nathan@yesenia.net', 'McKenziehaven'), (4, 'Patricia Lebsack', 'Julianne.OConner@kory.org', 'South Elvis'), (5, 'Chelsey Dietrich', 'Lucio_Hettinger@annie.ca', 'Roscoeview'), (6, 'Mrs. Dennis Schulist', 'Karley_Dach@jasper.info', 'South Christy'), (7, 'Kurtis Weissnat', 'Telly.Hoeger@billy.biz', 'Howemouth'), (8, 'Nicholas Runolfsdottir V', 'Sherwood@rosamond.me', 'Aliyaview'), (9, 'Glenna Reichert', 'Chaim_McDermott@dana.io', 'Bartholomebury'), (10, 'Clementina DuBuque', 'Rey.Padberg@karina.biz', 'Lebsackbury')"}
[tool-result-preview] {"ok": true, "data": {"rowcount": 10, "lastrowid": 10}, "error": null}

=== Iteration 4 ===
[assistant] Requested 1 tool call(s)
[tool-call] id=call_d0113c8b1b6648f49113563e name=execute_sql
[tool-args] {"query": "SELECT * FROM users"}
[tool-result-preview] {"ok": true, "data": {"columns": ["id", "name", "email", "city"], "rows": [{"id": 1, "name": "Leanne Graham", "email": "Sincere@april.biz", "city": "Gwenborough"}, {"id": 2, "name": "Ervin Howell", "email": "Shanna@melissa.tv", "city": "Wisokyburgh"}, {"id": 3, "name": "Clementine Bauch", "email": "Nathan@yesenia.net", "city": "McKenziehaven"}, {"id": 4, "name": "Patricia Lebsack", "email": "Julianne.OConner@kory.org", "city": "South Elvis"}, {"id": 5, "name": "Chelsey Dietrich", "email": "Lucio_Hettinger@annie.ca", "city": "Roscoeview"}, {"id": 6, "name": "Mrs. Dennis Schulist", "email": "Karley_Dach@jasper.info", "city": "South Christy"}, {"id": 7, "name": "Kurtis Weissnat", "email": "Telly.Hoeger@billy.biz", "city": "Howemouth"}, {"id": 8, "name": "Nicholas Runolfsdottir V", "email": "Sherwood@rosamond.me", "city": "Aliyaview"}, {"id": 9, "name": "Glenna Reichert", "email": "Chaim_McDermott@dana.io", "city": "Bartholomebury"}, {"id": 10, "name": "Clementina DuBuque", "email": "Rey.Padberg@karina.biz", "city": "Lebsackbury"}], "rowcount": 10}, "error": null}

=== Iteration 5 ===
[assistant-final]
I have successfully fetched the user data from the JSONPlaceholder API, created a SQLite table named `users`, and inserted the `id`, `name`, `email`, and `city` for all 10 users.

Here are the final contents of the `users` table:

| id | name | email | city |
| :--- | :--- | :--- | :--- |
| 1 | Leanne Graham | Sincere@april.biz | Gwenborough |
| 2 | Ervin Howell | Shanna@melissa.tv | Wisokyburgh |
| 3 | Clementine Bauch | Nathan@yesenia.net | McKenziehaven |
| 4 | Patricia Lebsack | Julianne.OConner@kory.org | South Elvis |
| 5 | Chelsey Dietrich | Lucio_Hettinger@annie.ca | Roscoeview |
| 6 | Mrs. Dennis Schulist | Karley_Dach@jasper.info | South Christy |
| 7 | Kurtis Weissnat | Telly.Hoeger@billy.biz | Howemouth |
| 8 | Nicholas Runolfsdottir V | Sherwood@rosamond.me | Aliyaview |
| 9 | Glenna Reichert | Chaim_McDermott@dana.io | Bartholomebury |
| 10 | Clementina DuBuque | Rey.Padberg@karina.biz | Lebsackbury |

[summary] iterations=5 final_text_preview=I have successfully fetched the user data from the JSONPlaceholder API, created a SQLite table named `users`, and inserted the `id`, `name`, `email`, and `city` for all 10 users. H...(truncated)
```

## 12. Anexo B - Verificación SQLite independiente (raw)

```text
1|Leanne Graham|Sincere@april.biz|Gwenborough
2|Ervin Howell|Shanna@melissa.tv|Wisokyburgh
3|Clementine Bauch|Nathan@yesenia.net|McKenziehaven
4|Patricia Lebsack|Julianne.OConner@kory.org|South Elvis
5|Chelsey Dietrich|Lucio_Hettinger@annie.ca|Roscoeview
6|Mrs. Dennis Schulist|Karley_Dach@jasper.info|South Christy
7|Kurtis Weissnat|Telly.Hoeger@billy.biz|Howemouth
8|Nicholas Runolfsdottir V|Sherwood@rosamond.me|Aliyaview
9|Glenna Reichert|Chaim_McDermott@dana.io|Bartholomebury
10|Clementina DuBuque|Rey.Padberg@karina.biz|Lebsackbury
```

---