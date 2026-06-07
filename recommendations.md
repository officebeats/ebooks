# Book Recommendations & Tally

This document acts as a tracking catalog for new AI and machine learning books you might want to buy or download as EPUB. Reprocessing is automated and will preserve your manually checked-off items.

## 🤖 Pending Recommendations
Here are the top newer releases in AI topics aggregated from Open Library, sorted by release date.

- [ ] [What Machines Can't Replace](https://openlibrary.org/works/OL45429525W) - _by Anna McPhee_ (2026)
- [ ] [Transforming Medicinal Plant Agriculture](https://openlibrary.org/works/OL45147574W) - _by Pankaj Kumar, Ashish R. Warghat_ (2026)
- [ ] [Tools of the Scribe](https://openlibrary.org/works/OL45148104W) - _by Brian Roark, Richard Sproat, Su-Youn Yoon_ (2026)
- [ ] [The Mind Behind The Machine](https://openlibrary.org/works/OL44867871W) - _by Artificial Intelligence_ (2026)
- [ ] [The Generative Revolution](https://openlibrary.org/works/OL44800016W) - _by Dr. Raffi Mohammed, L.L.S. MANEESHA, Dr. Prasad Babu Bairysetti, Dr. Chiranjeevi Aggala_ (2026)
- [ ] [The Dissemination and Evolution of Excellent Traditional Chinese Culture (ETCC) in the Age of Artificial Intelligence (AI)](https://openlibrary.org/works/OL45031090W) - _by You Chen_ (2026)
- [ ] [The Complete AIO Playbook](https://openlibrary.org/works/OL45098315W) - _by Unknown_ (2026)
- [ ] [The Art Book](https://openlibrary.org/works/OL44766535W) - _by Lori Randolph_ (2026)
- [ ] [Subjectivity Ethics and Governance of Ideological and Political Education in the Age of Artificial Intelligence](https://openlibrary.org/works/OL45154175W) - _by Jiayi Yuan_ (2026)
- [ ] [Soul Food and AI](https://openlibrary.org/works/OL45155417W) - _by Kala Allen Omeiza_ (2026)
- [ ] [Smart Manufacturing 5. 0](https://openlibrary.org/works/OL45148224W) - _by Daniel Alejandro Rossit, Foivos Psarommatis_ (2026)
- [ ] [Skin Cancer Detection Using Artificial Intelligence Techniques](https://openlibrary.org/works/OL45148505W) - _by Parikshit N. Mahalle, Nuzhat F Shaikh, Pritibala S. Ingle, Yashwant S. Ingle_ (2026)
- [ ] [Sentiment Analysis in NLP](https://openlibrary.org/works/OL45148906W) - _by Shanliang Yang_ (2026)
- [ ] [Second Draft](https://openlibrary.org/works/OL45158087W) - _by Dennis W. Butler_ (2026)
- [ ] [Scientific Machine Learning](https://openlibrary.org/works/OL45149284W) - _by Federico Pichi, Gianluigi Rozza, Maria Strazzullo, Davide Torlo_ (2026)
- [ ] [Salesforce AI](https://openlibrary.org/works/OL45154124W) - _by Joyce Kay Avila_ (2026)
- [ ] [Safeguarding Social Justice and Human Rights in the Age of AI](https://openlibrary.org/works/OL45151430W) - _by Sudershan Pasupuleti, Urmila Yadav_ (2026)
- [ ] [Revolutionizing Quick Commerce with AI Tools and Technologies](https://openlibrary.org/works/OL45151427W) - _by Nozha Erragcha, Rabia Romdhane_ (2026)
- [ ] [Reshaping Journalism and Communications with AI](https://openlibrary.org/works/OL45151401W) - _by Bünyamin Ayhan, Zehra Özkeçeci_ (2026)
- [ ] [Redefining Global Creative Sectors Through AI and Human Augmentation](https://openlibrary.org/works/OL45154157W) - _by Fazla Rabby, Sweta Thakur, Shafiqur Rahman, Nishita Pruthi, Mukesh Singla_ (2026)
- [ ] [Quantum AI](https://openlibrary.org/works/OL45543183W) - _by Unknown_ (2026)
- [ ] [Process of Generative AI Writing](https://openlibrary.org/works/OL45147771W) - _by Nathan Jung_ (2026)
- [ ] [Proceedings of 6th International Conference on Recent Trends in Machine Learning, IoT, Smart Cities and Applications](https://openlibrary.org/works/OL45149027W) - _by Vinit Kumar Gunjan, Jacek M. Zurada_ (2026)
- [ ] [Proceedings of 2025 International Conference on Artificial Intelligence and Autonomous Transportation](https://openlibrary.org/works/OL45148026W) - _by Jun Liu, Honghai Ji, Kailong Li, Shida Liu, Zhihui Hu_ (2026)
- [ ] [Predicting Injustice; Bias, Ethics, and the Machinery of Predictive Policing](https://openlibrary.org/works/OL45267578W) - _by Dr. Lincoln Eden_ (2026)
- [ ] [Philosophy of  Intelligence](https://openlibrary.org/works/OL45147595W) - _by Ermanno Bencivenga_ (2026)
- [ ] [Organizational Resilience and Artificial Intelligence](https://openlibrary.org/works/OL45148567W) - _by Arnab Mukherjee, Sachin Kumar_ (2026)
- [ ] [Optimization Techniques for Deep Learning](https://openlibrary.org/works/OL45149528W) - _by Atefeh Hemmati, Amir Masoud Rahmani, Fatemeh Bazikar, Hossein Moosaei, Panos M. Pardalos_ (2026)
- [ ] [Next-Generation Network Migration and Cloud Integration with Generative AI Scalable, Secure & Intelligent Hybrid Architectures for the Digital Era](https://openlibrary.org/works/OL45034706W) - _by Phani Santhosh Sivaraju_ (2026)
- [ ] [My Coworker Is a Robot](https://openlibrary.org/works/OL45147699W) - _by Jon Swartz_ (2026)

## 💾 Book Tally (Bought/Downloaded)
Below are the books you have successfully downloaded or purchased. Checked items here are automatically excluded from the recommendations list above when reprocessed.

_No books tallied yet. Check off items in the pending list and reprocess to see them move here!_

## 🔄 Reprocessing Guide
To refresh the recommendation database and clean up the list while keeping your checked items:
1. Open a terminal in this directory.
2. Run the recommendation script:
   ```bash
   python recommend_books.py
   ```
3. The script will parse this markdown file, preserve all `- [x]` items, filter out currently owned books in `books.json`, fetch new books, and update this file and `recommendations.json` automatically.
