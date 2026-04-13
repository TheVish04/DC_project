# 🌍 Our Awesome Distributed Note-Sharing Network! 🚀

Hello there! Welcome to the **P2P Notes** project. If you are wondering what this project is all about, you are in the right place!

We are going to explain everything about this project, step by step, as if you were 10 years old. Don't worry about big fancy words—we'll break them all down. Grab a juice box and let's go! 🧃

---

## 🤔 First of all, what is the Project?

Imagine you are in a big classroom with 50 students. Everyone takes their own notes for different subjects. Usually, if you want someone's notes, you have to ask them to print a copy, or maybe there's one giant locker (a central server) where everybody dumps their notes. But if the locker gets stuck or the key is lost, NOBODY gets notes. 😭

Instead, what if everyone just kept their own notebooks in their own bags? But, to know who has what, there is one giant **address book** at the front desk. 
- You look at the address book. 📖
- It says: *"Sally has the Science notes for Semester 2 in her bag."*
- You walk directly over to Sally and say, *"Hey, can I copy your Science notes?"*
- Sally says, *"Sure!"* and you copy them directly from her. 📝

**That is exactly what this project does!** But instead of notebooks and backpacks, it uses computers! It is a system where students (computers) share their digital notes directly with each other over the internet, while a directory (the Tracker) simply keeps track of who has what. 

---

## ⚡ What does "DC" mean and WHY is this a DC Project?

You might have heard the phrase **"DC Project"**. 
**DC** stands for **Distributed Computing**. 

### What is Distributed Computing? (The 10-year-old explanation)
Normally, when you use a website like YouTube or Netflix, all the videos are saved on giant supercomputers owned by one big company. You and millions of others connect to *their* computers to watch the video. This is called **Centralized Computing**. One big boss computer is doing all the heavy lifting.

But in **Distributed Computing**, there is NO big boss computer hoarding all the files! Instead, the work and the files are spread out across *everyone's* computers. The system works because a bunch of small computers team up to act like one giant computer! 

### Why is OUR project a "DC" project?
Because when someone uploads a notes file, it doesn't go to a magical cloud server owned by us. 
1. **The file stays on your computer!** 
2. Other people connect directly to **your computer** to download it. 
3. The computers form a cool "spider-web" connection together. We call this **P2P** (Peer-to-Peer). You are a "Peer" (a friend) sharing directly with another "Peer"!

This means we use the power of *everyone's* computer combined. Because the work is distributed (spread out) among everyone, it is literally a **Distributed Computing** project!

---

## 🧩 The Magic Parts: How is it Built?

Our project is divided into three main pieces:

1. **The Tracker 📍 (The Address Book)** 
   - This is the only central part. It DOES NOT store any files! It's super fast and lightweight. It only stores names and locations. It keeps an eye on who is online and what notes they own. Built with Python and MongoDB (a database).
   
2. **The Peer 💻 (Your Computer)**
   - This is the app that runs on your laptop. It talks to the Tracker to say "I'm online!" and it also talks directly to other Peers to say "Give me that file!". Built with Python.
   
3. **The Frontend 🎨 (The Beautiful Buttons)**
   - This is the webpage you click on. Without this, you'd have to type boring green code into a black screen. This gives you nice buttons, search bars, and colorful cards! Built with React.

### 🗺️ The Architecture Map (How it all connects)

```mermaid
graph TD
    classDef tracker fill:#f9f,stroke:#333,stroke-width:4px,color:#000;
    classDef peer fill:#bbf,stroke:#333,stroke-width:2px,color:#000;
    classDef ui fill:#bfb,stroke:#333,stroke-width:2px,color:#000;
    classDef db fill:#ff9,stroke:#333,stroke-width:2px,color:#000;

    Tracker["📍 Tracker (The Address Book)"]:::tracker
    DB[("🗄️ MongoDB (Stores Names & Locations)")]:::db
    
    subgraph "Your Computer"
        UI1["🎨 Frontend (Webpage)"]:::ui
        Peer1["💻 Peer 1 (Has Notes)"]:::peer
    end

    subgraph "Friend's Computer"
        UI2["🎨 Frontend (Webpage)"]:::ui
        Peer2["💻 Peer 2 (Needs Notes)"]:::peer
    end

    Tracker <-->|Reads / Writes| DB
    
    Peer1 -->|1. I am alive! Here are my files| Tracker
    Peer2 -->|2. Who has Math Notes?| Tracker
    Tracker -.->|3. Peer 1 has them!| Peer2
    
    Peer2 <==>|4. Direct Download! (P2P)| Peer1

    UI1 <-->|Clicks buttons| Peer1
    UI2 <-->|Clicks buttons| Peer2
```

---

## 🎬 Every Scenario Explained! 

Let's walk through literally every single thing that happens in this project, scenario by scenario. 

### Scenario 1: A New Friend Joins the Classroom (Peer Registration & Heartbeats)
**What happens:** You turn your computer on and open the app.
**The "DC" Magic:** Your computer (the Peer) immediately sends a message to the Address Book (Tracker) saying, *"Hey, I'm Peer 1, I am awake, and my IP address is this!"*. The Tracker writes your name down.
**But what if your computer crashes?** In Distributed Computing, computers break all the time. To fix this, your computer sends a "Heartbeat" (a tiny message saying *"I am still alive! 💓"*) every 10 seconds. If the Tracker doesn't hear a heartbeat from you for 30 seconds, it crosses your name off the list and tells everyone you went offline. You are safe!

### Scenario 2: You Want to Share Your Awesome Notes (File Announce)
**What happens:** You click "Upload", choose your PDF, type "Math Notes", and hit enter.
**The "DC" Magic:** Again, the file DOES NOT jump into the cloud. It stays neatly inside your `data` folder on your laptop. You slice the file into chunks. Then, your computer tells the Tracker: *"Hey! I have a file named Math Notes, and its secret fingerprint (hash code) is XYZ."* 
Now, everyone in the system knows you have it, but they haven't downloaded it yet!

### Scenario 3: Looking for Notes (Searching)
**What happens:** Another student, Bob, types "Math Notes" into his search bar. 
**The "DC" Magic:** Bob's computer asks the Tracker: *"Who has Math Notes?"*
The Tracker looks at its giant list and replies: *"Here's a list. Peer 1 (you) has it, and they are currently online!"* Bob's computer now knows exactly where to go. 

### Scenario 4: The Actual Download (P2P File Transfer)
**What happens:** Bob clicks the "Download" button on your Math Notes. 
**The "DC" Magic:** This is where the true Distributed Computing power shines! Bob's computer ignores the Tracker completely. Bob's computer builds a direct, invisible tunnel straight to YOUR computer. 
Bob says: *"Please give me chunk 1 of the Math Notes."*
Your computer says: *"Here you go!"*
Bob's computer saves it straight to his `downloads` folder. Now, *two* people have the math notes! If a third person wants them, they can download from Bob OR from you! The network just keeps getting stronger. 💪

### Scenario 5: The File is Missing! (Offline Peers)
**What happens:** Sally clicks on "History Notes", but the person who originally uploaded them turned off their laptop to go to bed. 😴
**The "DC" Magic:** The tracker realizes the person is offline (because their heartbeats stopped). It won't let Sally download it right now because the file is asleep on someone's laptop. But if Bob logged in, and Bob previously downloaded those history notes, Sally could download them directly from Bob instead! True teamwork!

---

## 🎓 Why is this super cool for developers?

If you are a bit older than 10 and want to know why we built it this way:

- **No Single Point of Failure (for storage):** By keeping files distributed, if one peer goes down, the system doesn't lose all the data forever, as long as someone else replicated the file!
- **Less Server Cost:** Storing terabytes of files on a central cloud database is super expensive! By storing them on user devices (peers), the server cost drops to almost 0. It only has to host lightweight text metadata!
- **Scalability:** As more users join, they bring more download power and storage space with them. The network gets really fast as it grows! 

---

## 🛠️ How to run it yourself! (For the Big Kids)

1. **Start the Tracker Server:** Go into the `tracker` folder and start the FastAPI server. It will connect to MongoDB to keep track of everyone.
2. **Start Peer 1:** Go into the `peer` folder, give it a unique port (like 9001), and start it. 
3. **Start Peer 2:** Open a new terminal, and start another peer on a different port (like 9002).
4. **Start the UI:** Go to the `frontend` folder, run `npm install` and `npm run dev`.

Now you can upload a file on Peer 1, and watch Peer 2 magically discover it and download it directly from Peer 1's computer folder to its own! 

---

### 🎉 Conclusion
And that's it! You've just learned what a **Distributed Computing Project** is! By having computers talk to each other as helpful friends instead of relying on one big boss-server, we created a magical, robust, and cost-free way to share knowledge. 

Now go share some notes! 📝✨
