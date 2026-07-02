"use client";

interface Counterparty {
  who: string;
  amount: number;
}

interface Props {
  title: string;
  items: Counterparty[];
}

export function TopCounterpartiesTable({ title, items }: Props) {
  return (
    <div className="mb-6">
      <h3 className="text-lg font-medium mb-2">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No data available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm table-auto">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Counterparty</th>
                <th className="px-3 py-2">Amount (KES)</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={idx} className="border-t">
                  <td className="px-3 py-2">{idx + 1}</td>
                  <td className="px-3 py-2">{it.who}</td>
                  <td className="px-3 py-2">{it.amount.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TopCounterpartiesTable;
