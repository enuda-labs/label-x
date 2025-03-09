# label-x

### This is the backend of the official LabelX Project

### Current Features

- to be added
- to be added

---

### Prerequisites

Before starting, ensure you have the following installed:

- Python (>= 3.10)
- pip
- Virtualenv/venv (recommended)
- PostgreSQL/MySQL (or any database of choice)

---

### Installation

Follow these steps to set up the project locally:

1.  **Clone the repository:**

    ```bash
     git clone https://github.com/enuda-labs/label-x
     cd label-x
    <br>

    ```

2.  **Create and activate a virtual environment:**

        <details>
        <summary>Windows</summary>


                python -m venv venv
               venv\\Scripts\\activate

        </details>


        <details>
        <summary>Linux/Mac</summary>


                python -m venv venv
                source venv/bin/activate
        </details>

    <br>

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    <br>

    ```

4.  **Create a `.env` file and set environment variables:**

    ````plaintext
    SECRET_KEY=your-secret-key
    DEBUG=False

        DATABASE_URL=your-database-url
        SENDER_EMAIL=xxxxxxxxx
        EMAIL_BACKEND=xxxxxxxxx
        EMAIL_HOST=xxxxxxxxx
        EMAIL_PORT=xxxxxxxxx
        EMAIL_USE_TLS=xxxxxxxxx
        EMAIL_HOST_USER=xxxxxxxxx
        EMAIL_HOST_PASSWORD=xxxxxxxxx

        ```

    <br>

    ````

5.  **Apply migrations:**

    ```bash
    python manage.py migrate
    <br>

    ```

6.  **Run the server:**
    ```bash
    python manage.py runserver
    ```

The server will be available at `http://127.0.0.1:8000/`.

---

<br>

---

### Testing

Run tests using the following command:

```bash
python manage.py test
```

---

### Contributing

To Contribute Follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Commit changes (`git commit -m "Add feature"`).
4. Push to the branch (`git push origin feature-branch`).
5. Open a Pull Request.

---

### License

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.

---

Contact

    •  Author Name: ......
    •  Email: ........
