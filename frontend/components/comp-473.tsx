import { useId } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const items = [
  {
    balance: "$1,250.00",
    email: "alex.t@company.com",
    id: "1",
    location: "San Francisco, US",
    name: "Alex Thompson",
    status: "Active",
  },
  {
    balance: "$600.00",
    email: "sarah.c@company.com",
    id: "2",
    location: "Singapore",
    name: "Sarah Chen",
    status: "Active",
  },
  {
    balance: "$650.00",
    email: "j.wilson@company.com",
    id: "3",
    location: "London, UK",
    name: "James Wilson",
    status: "Inactive",
  },
  {
    balance: "$0.00",
    email: "m.garcia@company.com",
    id: "4",
    location: "Madrid, Spain",
    name: "Maria Garcia",
    status: "Active",
  },
  {
    balance: "-$1,000.00",
    email: "d.kim@company.com",
    id: "5",
    location: "Seoul, KR",
    name: "David Kim",
    status: "Active",
  },
];

export default function Component() {
  const id = useId();
  return (
    <div>
      <div className="overflow-hidden rounded-md border bg-background">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="h-11">
                <Checkbox id={id} />
              </TableHead>
              <TableHead className="h-11">Name</TableHead>
              <TableHead className="h-11">Email</TableHead>
              <TableHead className="h-11">Location</TableHead>
              <TableHead className="h-11">Status</TableHead>
              <TableHead className="h-11 text-right">Balance</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Checkbox id={`table-checkbox-${item.id}`} />
                </TableCell>
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell>{item.email}</TableCell>
                <TableCell>{item.location}</TableCell>
                <TableCell>{item.status}</TableCell>
                <TableCell className="text-right">{item.balance}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter className="bg-transparent">
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={5}>Total</TableCell>
              <TableCell className="text-right">$2,500.00</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>
      <p className="mt-4 text-center text-muted-foreground text-sm">
        Card Table
      </p>
    </div>
  );
}
