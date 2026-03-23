# COMEX金在庫（Eligible / Registered / Pledged）

## 在庫区分の定義

COMEXの金在庫とは、取引所承認保管所（Exchange-approved depository）に保管されている金のことであり、在庫は主に3つに区分される。

| 区分 | 定義 | 受渡し可否 |
|------|------|-----------|
| **Eligible** | 先物受渡しの規格を満たしているが、warrantが未発行 | そのままでは不可 |
| **Registered** | Eligibleのうちwarrantが発行された金 | 可能 |
| **Pledged** | Registeredのうち、warrantがClearing Houseにperformance bondとして差入れ | 担保中のため自由に回せない |

## 規格適合とwarrant化の違い

重要なのは、**規格を満たしていることと、実際に受渡しに使えることは同じではない**点である。

- **Eligible** — 受渡し規格に合致した在庫だが、warrant未発行のため先物受渡しに直接使える状態ではない
- **Registered** — warrantが発行されており、先物の受渡しに用いることができる

CMEのwarranting解説では、warrantは取引所承認施設に保管された金属を表す**document of title**であり、保有者はclearing memberを通じて金属をwarrant化（register）でき、warrantは先物受渡しを開始するために使われると説明されている。

金地金がCOMEXの受渡し対象となるには、**契約仕様・承認ブランド・承認保管所での保管**などの条件を満たす必要があり、そのうえでwarrantが発行されてRegisteredになって初めて、先物受渡しに使える状態になる。

## 実務上の読み方

実務上は以下のように整理すると分かりやすい:

- **Registered在庫** → 「今すぐ受渡しに回しやすい在庫」
- **Eligible在庫** → 「規格上は使えるが、まだ受渡し用に登録されていない潜在在庫」
- **Pledged** → Registeredの一部だが、担保差入れ中のため自由に受渡しへ回せない

受渡し逼迫や現物需給の強さをみる際は、総在庫だけでなく**Registered在庫の水準や増減**を見る方が実務的に有用である。

## 実務上の確認ポイント

COMEX金在庫を見るときは、単純な総量よりも以下を確認する方が有用:

1. **Registered在庫が増えているか減っているか**
2. **EligibleからRegisteredへ転換できる余地**がどの程度あるか
3. **Pledgedが多く、自由在庫が細っていないか**

受渡しそのものは口座保有者同士が直接行うのではなく、**clearing firm間でwarrantを通じて**行われるため、在庫の「規格適合」と「warrant化」は区別して考える必要がある。CMEのルールでも、施設は日次でregistered・pledged・eligibleの数量と、その受入・出荷数量を報告することが求められている。
